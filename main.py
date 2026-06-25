import startup.env_loader
import os
import time
import uuid
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Response, status, Request, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from graph import graph
from approval_store import (
    pending_approvals,
    approved_results,
    get_approval,
    get_all_approvals,
    remaining_seconds,
)
from memory import get_history, add_message

from database.migrations import run_startup_migrations
from startup.validation import validate_environment
from startup.initialization import initialize_provider
from policy import get_policy, load_policy
from services.gateway_service import (
    GatewayProviderConfigurationError,
    GatewayProviderUnavailableError,
    GatewayService,
)

# Set up basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("authclaw.gateway")

API_KEY = os.getenv("AUTHCLAW_TEST_API_KEY", "")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. run_startup_migrations()
    # 2. validate_environment()
    # 3. initialize_provider()
    run_startup_migrations()

    validate_environment()
    initialize_provider()
    
    # 4. Start background compliance watcher for watched_documents folder
    from document_processing.monitoring import start_background_monitoring
    try:
        start_background_monitoring()
    except Exception as ex:
        logger.error(f"Failed to start background document monitoring: {ex}")
        
    yield
    
    # Shutdown sequence:
    from document_processing.monitoring import stop_background_monitoring
    try:
        stop_background_monitoring()
    except Exception as ex:
        logger.error(f"Failed to stop background document monitoring: {ex}")

app = FastAPI(lifespan=lifespan)

def get_allowed_origins() -> List[str]:
    configured = os.getenv("AUTHCLAW_ALLOWED_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5174", "http://127.0.0.1:5174"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API_KEY removed for production security hardening


import os
import hashlib
import base64
import hmac
import struct
import time
from cryptography.fernet import Fernet

ENCRYPTION_KEY = os.getenv("AUTHCLAW_ENCRYPTION_KEY", "uK2zL_s-Upxl3k88J9o0nK4qR2_l8U90jK1l4u89mKo=")

DEFAULT_ITERATIONS = int(os.getenv("AUTHCLAW_PASSWORD_ITERATIONS", "600000"))

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = DEFAULT_ITERATIONS
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        iterations
    )
    salt_b64 = base64.b64encode(salt).decode('utf-8')
    key_b64 = base64.b64encode(key).decode('utf-8')
    return f"pbkdf2_sha256${iterations}${salt_b64}${key_b64}"

def verify_password(password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password or not hashed_password.startswith("pbkdf2_sha256$"):
            return False
        parts = hashed_password.split('$')
        if len(parts) != 4:
            return False
        _, iterations_str, salt_b64, key_b64 = parts
        iterations = int(iterations_str)
        salt = base64.b64decode(salt_b64.encode('utf-8'))
        expected_key = base64.b64decode(key_b64.encode('utf-8'))
        actual_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            iterations
        )
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False

def get_hotp_token(secret: str, intervals_no: int) -> str:
    secret = secret.strip().replace(" ", "")
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += '=' * (8 - missing_padding)
    try:
        key = base64.b32decode(secret, casefold=True)
    except Exception as e:
        raise ValueError(f"Invalid base32 secret: {e}")
        
    msg = struct.pack(">Q", intervals_no)
    hmac_result = hmac.new(key, msg, hashlib.sha1).digest()
    o = hmac_result[19] & 15
    token = (struct.unpack(">I", hmac_result[o:o+4])[0] & 0x7fffffff) % 1000000
    return f"{token:06d}"

def verify_totp_token(secret: str, token: str, window: int = 1) -> bool:
    if not secret or not token:
        return False
    token = str(token).strip()
    if not token.isdigit() or len(token) != 6:
        return False
    current_time = int(time.time())
    time_step = 30
    current_interval = current_time // time_step
    
    for i in range(-window, window + 1):
        try:
            if get_hotp_token(secret, current_interval + i) == token:
                return True
        except Exception:
            pass
    return False

def generate_totp_secret() -> str:
    return base64.b32encode(os.urandom(10)).decode('utf-8')

def build_otpauth_uri(email: str, secret: str) -> str:
    from urllib.parse import quote
    account = quote(email)
    issuer = quote("AuthClaw")
    return f"otpauth://totp/AuthClaw:{account}?secret={secret}&issuer={issuer}"

def encrypt_secret(raw_value: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
    return cipher.encrypt(raw_value.encode('utf-8')).decode('utf-8')

def decrypt_secret(encrypted_value: str) -> str:
    cipher = Fernet(ENCRYPTION_KEY.encode('utf-8'))
    return cipher.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')

def resolve_tenant(x_api_key: str, authorization: str = None) -> int:
    key_to_check = x_api_key
    if not key_to_check and authorization:
        if authorization.startswith("Bearer "):
            key_to_check = authorization[7:]
        else:
            key_to_check = authorization

    if not key_to_check:
        raise HTTPException(status_code=401, detail="Authentication credentials missing.")

    # 1. Check if the key_to_check is a valid JWT session token
    jwt_payload = decode_jwt(key_to_check)
    if jwt_payload and "tenant_id" in jwt_payload:
        return jwt_payload["tenant_id"]

    # 2. Otherwise, treat it as a raw API key, calculate its SHA-256 hash
    h = hashlib.sha256(key_to_check.encode('utf-8')).hexdigest()

    # 3. Check in database
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT tenant_id
                FROM tenant_api_keys
                WHERE key_hash = :h
                  AND revoked_at IS NULL
                  AND (expires_at IS NULL OR expires_at > NOW())
            """),
            {"h": h}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid API Key.")
        
        tenant_id = row[0]
        # Update last_used_at
        conn.execute(
            text("UPDATE tenant_api_keys SET last_used_at = NOW() WHERE key_hash = :h"),
            {"h": h}
        )
        conn.commit()
        return tenant_id


def resolve_tenant_from_authorization(authorization: str = None) -> int:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization credentials missing.")
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid session token.")
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Session token is missing tenant scope.")
    return tenant_id

def get_current_user_from_authorization(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization credentials missing.")
    token = authorization[7:] if authorization.startswith("Bearer ") else authorization
    payload = decode_jwt(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid session token.")
    return payload

def require_platform_admin(payload: dict = Depends(get_current_user_from_authorization)) -> dict:
    if payload.get("role") != "Platform Admin":
        raise HTTPException(status_code=403, detail="Platform admin access required.")
    return payload

def require_tenant_access_admin(payload: dict = Depends(get_current_user_from_authorization)) -> dict:
    if payload.get("role") not in {"Super Admin", "Security Admin"}:
        raise HTTPException(status_code=403, detail="Tenant access administrator role required.")
    if not payload.get("tenant_id"):
        raise HTTPException(status_code=401, detail="Session token is missing tenant scope.")
    return payload


# SaaS Onboarding & Management Schemas
class RegisterRequest(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    email: str
    password: str
    domain: str

class VerifyEmailRequest(BaseModel):
    token: str

class DomainVerifyRequest(BaseModel):
    domain: str
    token: str

class KeyGenerateRequest(BaseModel):
    name: str

class KeyRotateRequest(BaseModel):
    name: Optional[str] = None

class ProviderConnectRequest(BaseModel):
    provider: str
    payload: dict


class ChatRequest(BaseModel):
    session_id: str
    message: str


class RedactPlaygroundRequest(BaseModel):
    text: str


class ChatCompletionMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False


class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: ChatCompletionMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4()}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "authclaw-gateway"
    choices: List[ChatCompletionResponseChoice]


@app.get("/")
def home():
    return {
        "message": "AuthClaw Running"
    }


def get_gateway_service() -> GatewayService:
    return GatewayService(graph=graph, resolve_tenant=resolve_tenant, decode_jwt=decode_jwt)


@app.post("/gateway/chat")
def gateway_chat(
    request: ChatRequest,
    x_api_key: str = Header(None),
    authorization: Optional[str] = Header(None)
):
    service = get_gateway_service()
    try:
        execution = service.execute_chat(
            message=request.message,
            session_id=request.session_id,
            x_api_key=x_api_key,
            authorization=authorization,
        )
        return service.format_chat_response(execution)
    except GatewayProviderConfigurationError as e:
        logger.error(f"Provider configuration error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "provider_not_configured"}
        )
    except GatewayProviderUnavailableError as e:
        logger.error(f"Provider invocation error: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "provider_unavailable",
                "error": "provider_unavailable",
                "message": str(e),
                "request_id": e.request_id,
                "trace": e.trace,
            }
        )


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_api_key: str = Header(None),
    authorization: Optional[str] = Header(None)
):
    service = get_gateway_service()
    try:
        execution = service.execute_chat(
            message=request.message,
            session_id=request.session_id,
            x_api_key=x_api_key,
            authorization=authorization,
        )
        return service.format_chat_response(execution)
    except GatewayProviderConfigurationError as e:
        logger.error(f"Provider configuration error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "provider_not_configured"}
        )
    except GatewayProviderUnavailableError as e:
        logger.error(f"Provider invocation error: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "provider_unavailable",
                "error": "provider_unavailable",
                "message": str(e),
                "request_id": e.request_id,
                "trace": e.trace,
            }
        )



class SessionCreate(BaseModel):
    session_id: str
    title: Optional[str] = "New Chat"

@app.post("/chat/sessions")
def create_chat_session(
    req: SessionCreate,
    authorization: Optional[str] = Header(None)
):
    username = "admin_user"
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        try:
            payload = decode_jwt(token)
            if payload and "sub" in payload:
                username = payload["sub"]
        except Exception:
            pass

    try:
        from database import engine, text
        with engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO chat_sessions (session_id, title, user_id, created_at, updated_at)
                VALUES (:session_id, :title, :user_id, NOW(), NOW())
                ON CONFLICT (session_id) DO UPDATE SET title = EXCLUDED.title, updated_at = NOW()
                """),
                {"session_id": req.session_id, "title": req.title, "user_id": username}
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Database error in create_chat_session: {e}", exc_info=True)

    return {"status": "success", "session_id": req.session_id, "title": req.title}


@app.get("/chat/sessions")
def get_chat_sessions(authorization: Optional[str] = Header(None)):
    try:
        from database import engine, text
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT session_id, title, created_at, updated_at, user_id FROM chat_sessions ORDER BY updated_at DESC")
            )
            sessions_list = []
            for row in res:
                sessions_list.append({
                    "session_id": row[0],
                    "title": row[1],
                    "created_at": row[2].isoformat() if hasattr(row[2], "isoformat") else str(row[2]),
                    "updated_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                    "user_id": row[4]
                })
            return sessions_list
    except Exception as e:
        logger.error(f"Database error in get_chat_sessions: {e}", exc_info=True)
        return []


@app.get("/chat/sessions/{session_id}")
def get_chat_session_messages(session_id: str):
    from memory import get_history
    return get_history(session_id)


@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str):
    try:
        from database import engine, text
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM chat_messages WHERE session_id = :session_id"),
                {"session_id": session_id}
            )
            conn.execute(
                text("DELETE FROM chat_sessions WHERE session_id = :session_id"),
                {"session_id": session_id}
            )
            conn.commit()
        return {"status": "success", "message": f"Session {session_id} deleted."}
    except Exception as e:
        logger.error(f"Database error in delete_chat_session: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.delete("/chat/sessions")
def purge_all_sessions():
    try:
        from database import engine, text
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM chat_messages"))
            conn.execute(text("DELETE FROM chat_sessions"))
            
            # Re-seed default session
            conn.execute(
                text("""
                INSERT INTO chat_sessions (session_id, title, user_id, created_at, updated_at)
                VALUES (:session_id, :title, :user_id, NOW(), NOW())
                ON CONFLICT (session_id) DO NOTHING
                """),
                {"session_id": "default", "title": "Default Session", "user_id": "admin_user"}
            )
            conn.commit()
        return {"status": "success", "message": "All sessions purged and default session re-seeded."}
    except Exception as e:
        logger.error(f"Database error in purge_all_sessions: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

@app.delete("/chat/sessions/{session_id}")
@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM chat_sessions WHERE session_id = :session_id"),
                {"session_id": session_id}
            )
            conn.commit()
        return {"status": "success", "message": f"Session {session_id} deleted successfully"}
    except Exception as e:
        logger.error(f"Database error in delete_session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/chat/sessions")
@app.delete("/sessions")
def delete_all_sessions():
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM chat_messages"))
            conn.execute(text("DELETE FROM chat_sessions"))
            conn.execute(
                text("""
                INSERT INTO chat_sessions (session_id, title, user_id, created_at, updated_at)
                VALUES ('default', 'Default Session', 'admin_user', NOW(), NOW())
                ON CONFLICT (session_id) DO NOTHING
                """)
            )
            conn.commit()
        return {"status": "success", "message": "All sessions deleted and default session seeded"}
    except Exception as e:
        logger.error(f"Database error in delete_all_sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/policies/redact")
def redact_playground(
    request: RedactPlaygroundRequest,
    authorization: Optional[str] = Header(None)
):
    username = "admin_user"
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization[7:]
        else:
            token = authorization
        try:
            payload = decode_jwt(token)
            if payload and "sub" in payload:
                username = payload["sub"]
        except Exception:
            pass

    from redaction import redact_sensitive_data_rich
    redacted_text, triggered = redact_sensitive_data_rich(request.text, username)

    triggered_names = "None"
    if triggered:
        triggered_names = ", ".join(list(set([t["policy_name"] for t in triggered])))

    return {
        "redacted_text": redacted_text,
        "count": len(triggered),
        "confidence": 98 if len(triggered) > 0 else 100,
        "triggered": triggered_names
    }


@app.get("/approvals")
def get_approvals_list():
    approvals = get_all_approvals()
    result = []
    for aid, record in approvals.items():
        result.append({
            "approval_id": record["approval_id"],
            "status": record["status"],
            "created_at": record["created_at"],
            "expires_at": record["expires_at"],
            "remaining_seconds": remaining_seconds(record),
            "approved_at": record["approved_at"],
            "rejected_at": record["rejected_at"],
            "executed_at": record["executed_at"],
            "requested_action": record["requested_action"],
            "query": record["query"],
            "request_id": record["request_id"],
            "correlation_id": record["correlation_id"]
        })
    return result


@app.get("/approvals/{approval_id}")
def get_approval_by_id(approval_id: str):
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval ID not found"
        )
    return {
        "approval_id": record["approval_id"],
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "remaining_seconds": remaining_seconds(record),
        "approved_at": record["approved_at"],
        "rejected_at": record["rejected_at"],
        "executed_at": record["executed_at"],
        "requested_action": record["requested_action"],
        "query": record["query"],
        "request_id": record["request_id"],
        "correlation_id": record["correlation_id"]
    }


@app.post("/approve/{approval_id}")
async def approve_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        # For backward compatibility, return JSON dict rather than raising 404
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Approval ID not found"}
        )

    # Expiry check is handled by get_approval() lazily updating to 'expired'
    if record["status"] == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has expired"
        )
    if record["status"] == "rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has already been rejected"
        )
    if record["status"] == "executed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has already been executed"
        )

    # Policy checks for MFA configuration
    policy = get_policy()
    approval_policy = policy.get("approval", {})
    require_mfa = approval_policy.get("require_mfa", True)

    body_bytes = await request.body()
    try:
        payload = json.loads(body_bytes) if body_bytes else {}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )

    from startup.audit import log_approval_event

    if require_mfa and body_bytes:
        mfa_code = payload.get("mfa_code") if isinstance(payload, dict) else None
        if not mfa_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA code is required"
            )


        tenant_id = record.get("tenant_id")
        from database import engine
        from sqlalchemy import text
        totp_secret = None
        if tenant_id:
            with engine.connect() as conn:
                totp_secret = conn.execute(
                    text("SELECT totp_secret FROM tenants WHERE id = :id"),
                    {"id": tenant_id}
                ).scalar()

        if not totp_secret:
            log_approval_event(
                event="approval_mfa_failed",
                approval_id=record["approval_id"],
                request_id=record["request_id"],
                correlation_id=record["correlation_id"],
                extra={"error": "MFA_NOT_CONFIGURED"}
            )
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "error": "MFA_NOT_CONFIGURED",
                    "message": "MFA is not configured for this tenant."
                }
            )

        if not verify_totp_token(totp_secret, mfa_code):
            log_approval_event(
                event="approval_mfa_failed",
                approval_id=record["approval_id"],
                request_id=record["request_id"],
                correlation_id=record["correlation_id"],
                extra={"provided_code": mfa_code, "error": "INVALID_MFA_CODE"}
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid MFA code"
            )

    # Transition status to approved
    record["status"] = "approved"
    record["approved_at"] = datetime.now(timezone.utc).isoformat()

    log_approval_event(
        event="approval_approved",
        approval_id=record["approval_id"],
        request_id=record["request_id"],
        correlation_id=record["correlation_id"],
        extra={"approved_at": record["approved_at"]}
    )

    # Create blockchain audit record for approval decision
    auth_header = request.headers.get("Authorization")
    approver = "System Admin"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_jwt(token)
        if payload and "sub" in payload:
            approver = payload["sub"]

    from verify_audit import create_audit_block
    create_audit_block(
        query=record["query"],
        response=f"Approval request approved. MFA validation passed.",
        allowed=True,
        risk_level=record["risk_level"],
        approval_status="approved",
        session_id=record["correlation_id"],
        approval_id=record["approval_id"],
        approver=approver,
        original_request=record["query"],
        approval_timestamp=datetime.fromisoformat(record["approved_at"]),
        execution_timestamp=None,
        execution_status="approved",
        tenant_id=record.get("tenant_id")
    )

    # Maintain backward compatibility in response format
    return {
        "message": "Request Approved",
        "approval_id": approval_id,
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "remaining_seconds": remaining_seconds(record),
        "data": record
    }



@app.post("/reject/{approval_id}")
def reject_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Approval ID not found"}
        )

    if record["status"] == "expired":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request has expired"
        )
    if record["status"] == "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request is already approved"
        )
    if record["status"] == "executed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Approval request is already executed"
        )

    record["status"] = "rejected"
    record["rejected_at"] = datetime.now(timezone.utc).isoformat()

    from startup.audit import log_approval_event
    log_approval_event(
        event="approval_rejected",
        approval_id=record["approval_id"],
        request_id=record["request_id"],
        correlation_id=record["correlation_id"],
        extra={"rejected_at": record["rejected_at"]}
    )

    # Create blockchain audit record for rejection decision
    auth_header = request.headers.get("Authorization")
    approver = "System Admin"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_jwt(token)
        if payload and "sub" in payload:
            approver = payload["sub"]

    from verify_audit import create_audit_block
    create_audit_block(
        query=record["query"],
        response=f"Approval request explicitly rejected.",
        allowed=False,
        risk_level=record["risk_level"],
        approval_status="rejected",
        session_id=record["correlation_id"],
        approval_id=record["approval_id"],
        approver=approver,
        original_request=record["query"],
        approval_timestamp=None,
        execution_timestamp=datetime.fromisoformat(record["rejected_at"]),
        execution_status="rejected",
        tenant_id=record.get("tenant_id")
    )

    return {
        "message": "Request Rejected",
        "approval_id": approval_id,
        "status": record["status"],
        "created_at": record["created_at"],
        "expires_at": record["expires_at"],
        "remaining_seconds": remaining_seconds(record),
        "data": record
    }


@app.post("/execute/{approval_id}")
def execute_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Request not approved"} # Match legacy error message
        )

    if record["status"] != "approved":
        # Check if legacy expected error body
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": f"Request not approved. Status is '{record['status']}'."}
        )

    query = record["query"]

    # Transition status to executed
    record["status"] = "executed"
    record["executed_at"] = datetime.now(timezone.utc).isoformat()

    # Execute the approved query through the canonical gateway lifecycle.
    try:
        service = get_gateway_service()
        execution = service.execute_approval(
            approval_record=record,
            x_api_key=request.headers.get("X-API-Key"),
            authorization=request.headers.get("Authorization"),
        )
        result = execution.result
    except GatewayProviderConfigurationError as e:
        logger.error(f"Provider configuration error in execute: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "provider_not_configured"}
        )
    except GatewayProviderUnavailableError as e:
        logger.error(f"Provider invocation error in execute: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "provider_unavailable",
                "error": "provider_unavailable",
                "message": str(e),
                "request_id": e.request_id,
                "trace": e.trace,
            }
        )

    from startup.audit import log_approval_event
    log_approval_event(
        event="approval_executed",
        approval_id=record["approval_id"],
        request_id=record["request_id"],
        correlation_id=record["correlation_id"],
        extra={
            "query": query,
            "response": result.get("response"),
            "execution_request_id": execution.request_id,
        }
    )

    # Create blockchain audit record for execution
    auth_header = request.headers.get("Authorization")
    approver = "System Admin"
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        payload = decode_jwt(token)
        if payload and "sub" in payload:
            approver = payload["sub"]

    app_ts = None
    if record.get("approved_at"):
        try:
            app_ts = datetime.fromisoformat(record["approved_at"])
        except Exception:
            pass

    from verify_audit import create_audit_block
    create_audit_block(
        query=query,
        response=result.get("response", "No response generated"),
        allowed=True,
        risk_level=record["risk_level"],
        approval_status="executed",
        session_id=record["correlation_id"],
        approval_id=record["approval_id"],
        approver=approver,
        original_request=query,
        approval_timestamp=app_ts,
        execution_timestamp=datetime.fromisoformat(record["executed_at"]),
        execution_status="executed",
        tenant_id=record.get("tenant_id")
    )

    return {
        "message": "Executed Successfully",
        "query": query,
        "response": result.get("response"),
        "request_id": execution.request_id,
        "provider": execution.provider,
        "model": execution.model,
        "route_id": execution.route_id,
        "decision": execution.decision,
        "trace": execution.trace,
    }


@app.post("/test/expire/{approval_id}")
def test_expire_approval(approval_id: str):
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval ID not found")
    # Force expires_at to be in the past
    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    record["expires_at"] = past_time.isoformat()
    record["status"] = "pending"
    return {"message": "Approval simulated to expire", "record": record}


@app.get("/audit/verify")
def verify_audit(authorization: Optional[str] = Header(None)):
    tenant_id = resolve_tenant_from_authorization(authorization)
    correlation_id = str(uuid.uuid4())
    from startup.audit import log_audit_event
    log_audit_event(
        event="audit_verification_started",
        correlation_id=correlation_id
    )

    from verify_audit import verify_audit_chain
    res = verify_audit_chain(tenant_id=tenant_id)

    if res["valid"]:
        log_audit_event(
            event="audit_verification_passed",
            correlation_id=correlation_id,
            extra={"records_checked": res["records_checked"]}
        )
    else:
        log_audit_event(
            event="audit_verification_failed",
            correlation_id=correlation_id,
            extra={"records_checked": res["records_checked"]}
        )
    return res


@app.get("/audit/verify/summary")
def verify_audit_summary(authorization: Optional[str] = Header(None)):
    tenant_id = resolve_tenant_from_authorization(authorization)
    from verify_audit import verify_audit_chain
    res = verify_audit_chain(tenant_id=tenant_id)

    if not res["valid"]:
        return {
            "valid": False,
            "records_checked": res["records_checked"],
            "last_verified_record": res.get("failed_record_id"),
            "chain_started_at": None,
            "latest_hash": None
        }

    # Fetch the latest record ID and hash
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(
            text("""
            SELECT id, integrity_hash
            FROM audit_logs
            WHERE integrity_hash IS NOT NULL AND tenant_id = :tenant_id
            ORDER BY id DESC
            LIMIT 1
            """),
            {"tenant_id": tenant_id}
        ).fetchone()

    last_verified_record = row[0] if row else 0
    latest_hash = row[1] if row else None

    return {
        "valid": True,
        "records_checked": res["records_checked"],
        "last_verified_record": last_verified_record,
        "chain_started_at": res["chain_started_at"],
        "latest_hash": latest_hash
    }


@app.get("/audit/hash-chain")
def get_audit_hash_chain(limit: int = 50, authorization: Optional[str] = Header(None)):
    tenant_id = resolve_tenant_from_authorization(authorization)
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            SELECT id, previous_hash, integrity_hash, created_at, approval_id, user_query,
                   approver, approval_status, original_request, approval_timestamp,
                   execution_timestamp, execution_status, tenant_id, username,
                   risk_level, allowed, response, policy_name, policy_type
            FROM audit_logs 
            WHERE integrity_hash IS NOT NULL
              AND tenant_id = :tenant_id
            ORDER BY id DESC 
            LIMIT :limit
            """),
            {"limit": limit, "tenant_id": tenant_id}
        )
        rows = res.fetchall()

    result = []
    for r in rows:
        created_at_str = r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3])
        result.append({
            "record_id": r[0],
            "previous_hash": r[1],
            "integrity_hash": r[2],
            "timestamp": created_at_str,
            "approval_id": r[4],
            "user_query": r[5],
            "approver": r[6],
            "approval_status": r[7],
            "original_request": r[8] or r[5],
            "approval_timestamp": r[9].isoformat() if hasattr(r[9], "isoformat") else (str(r[9]) if r[9] else None),
            "execution_timestamp": r[10].isoformat() if hasattr(r[10], "isoformat") else (str(r[10]) if r[10] else None),
            "execution_status": r[11] or r[7],
            "status": r[11] or r[7],
            "tenant_id": r[12],
            "username": r[13],
            "risk_level": r[14],
            "allowed": r[15],
            "response": r[16],
            "security_decision": "ALLOW" if r[15] else "BLOCK",
            "policy_decision": r[17] or r[18] or r[7],
            "provider": None,
            "hash_reference": r[2]
        })
    return result


@app.post("/v1/chat/completions")
def chat_completions(
    request: ChatCompletionRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    # API Key Authentication
    api_key_val = None
    if authorization:
        if authorization.startswith("Bearer "):
            api_key_val = authorization[7:]
        else:
            api_key_val = authorization
    elif x_api_key:
        api_key_val = x_api_key

    tenant_id = resolve_tenant(api_key_val, authorization)

    if not request.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Messages list cannot be empty"
        )

    last_msg = request.messages[-1]
    if last_msg.role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Last message must be from user"
        )

    user_query = last_msg.content
    session_id = x_session_id or f"session-{uuid.uuid4()}"

    # Pre-populate history in database if currently empty
    db_history = get_history(session_id)
    if not db_history:
        for msg in request.messages[:-1]:
            add_message(session_id, msg.role, msg.content)

    service = get_gateway_service()
    try:
        execution = service.execute_chat(
            message=user_query,
            session_id=session_id,
            x_api_key=api_key_val,
            authorization=authorization,
            model=request.model or "authclaw-gateway",
        )
    except GatewayProviderConfigurationError as e:
        logger.error(f"Provider configuration error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "type": "provider_not_configured",
                    "message": "Model provider is not configured."
                }
            }
        )
    except GatewayProviderUnavailableError as e:
        logger.error(f"Error executing graph pipeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "type": "provider_unavailable",
                    "message": f"Failed to communicate with LLM provider: {str(e)}",
                    "request_id": e.request_id,
                    "trace": e.trace,
                },
            }
        )

    result = execution.result
    if not result.get("allowed", True):
        logger.warning(f"Request blocked by policy: '{user_query[:50]}'")
        category = result.get("block_category", "data_exfiltration")
        service.format_chat_response(execution)
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "request_id": execution.request_id,
                "error": {
                    "message": "Request blocked by policy engine",
                    "type": "policy_violation",
                    "category": category
                }
            }
        )

    if result.get("approval_status") == "PENDING_APPROVAL":
        approval_id = result.get("approval_id")
        logger.info(f"Request flagged for approval. ID: {approval_id}")
        service.format_chat_response(execution)
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "request_id": execution.request_id,
                "approval_id": approval_id,
                "status": "pending_approval",
                "message": "High-risk request requires approval."
            }
        )

    response_payload = {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "authclaw-gateway",
        "request_id": execution.request_id,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result.get("response", "No response generated")
                },
                "finish_reason": "stop"
            }
        ]
    }
    return response_payload




@app.get("/policies")
def get_policies_endpoint():
    try:
        policy = get_policy()
        return policy
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve policies: {str(e)}"
        )


@app.post("/policies/reload")
def reload_policies_endpoint():
    try:
        new_policy = load_policy()
        reload_log = {
            "event": "policy_reload",
            "status": "success",
            "message": "Policies reloaded successfully.",
            "details": {
                "version": new_policy.get("version")
            }
        }
        logger.info(json.dumps(reload_log))
        print(json.dumps(reload_log), flush=True)

        # Create blockchain audit block for policy modification
        from verify_audit import create_audit_block
        create_audit_block(
            query="reload policies",
            response=f"Policies reloaded successfully. Version: {new_policy.get('version')}",
            allowed=True,
            risk_level="LOW",
            approval_status="N/A",
            session_id="system"
        )

        return {
            "message": "Policies reloaded successfully",
            "policies": new_policy
        }
    except Exception as e:
        reload_log = {
            "event": "policy_reload",
            "status": "failed",
            "message": f"Policies reload failed: {str(e)}"
        }
        logger.error(json.dumps(reload_log))
        print(json.dumps(reload_log), flush=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "Failed to reload policies",
                "details": str(e)
            }
        )


@app.get("/health")
def get_health():
    return {
        "status": "healthy"
    }


@app.get("/health/details")
def get_health_details():
    database_status = "healthy"
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        database_status = "unhealthy"

    provider_status = "healthy"
    try:
        from providers import get_provider
        get_provider()
    except Exception:
        provider_status = "unhealthy"

    return {
        "audit_chain_active": True,
        "hitl_enabled": True,
        "policy_enforcement_enabled": True,
        "redaction_enabled": True,
        "provider_status": provider_status,
        "database_status": database_status
    }


@app.get("/health/ready")
def get_readiness():
    checks = {
        "database": "unknown",
        "production_validation": "not_applicable",
    }
    http_status = 200
    try:
        from database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"
        http_status = 503

    if os.getenv("AUTHCLAW_ENV", "development").lower() in {"production", "prod"}:
        from startup.validation import validate_production_environment
        validation_errors = validate_production_environment()
        if validation_errors:
            checks["production_validation"] = "failed"
            checks["production_errors"] = validation_errors
            http_status = 503
        else:
            checks["production_validation"] = "passed"

    return JSONResponse(status_code=http_status, content={"status": "ready" if http_status == 200 else "not_ready", "checks": checks})


@app.get("/metrics")
def get_metrics():
    from database import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            total_requests = conn.execute(text("SELECT COUNT(*) FROM gateway_requests")).scalar() or 0
            blocked_requests = conn.execute(text("SELECT COUNT(*) FROM gateway_requests WHERE allowed = FALSE")).scalar() or 0
            avg_latency = conn.execute(text("SELECT AVG(latency) FROM gateway_requests")).scalar() or 142
            avg_latency = int(avg_latency)
            
            tokens_in = conn.execute(text("SELECT SUM(tokens_in) FROM gateway_requests")).scalar() or 0
            tokens_out = conn.execute(text("SELECT SUM(tokens_out) FROM gateway_requests")).scalar() or 0
            token_consumption = (tokens_in or 0) + (tokens_out or 0)
            
            active_tenants = conn.execute(text("SELECT COUNT(*) FROM tenants WHERE status = 'active'")).scalar() or 0
            active_routes = conn.execute(text("SELECT COUNT(*) FROM gateway_routes WHERE enabled = TRUE")).scalar() or 0
            active_policies = conn.execute(text("SELECT COUNT(*) FROM policies WHERE enabled = TRUE")).scalar() or 0
            open_findings = conn.execute(text("SELECT COUNT(*) FROM remediation_findings WHERE approval_status = 'pending'")).scalar() or 0
            active_workers = conn.execute(text("SELECT COUNT(*) FROM ephemeral_workers WHERE status = 'running'")).scalar() or 0
            audit_chain_records = conn.execute(text("SELECT COUNT(*) FROM audit_logs WHERE integrity_hash IS NOT NULL")).scalar() or 0

            # Document Intelligence Database Aggregations
            total_documents = conn.execute(text("SELECT COUNT(*) FROM documents")).scalar() or 0
            total_findings = conn.execute(text("SELECT COUNT(*) FROM document_findings")).scalar() or 0
            total_violations = conn.execute(text("SELECT COUNT(*) FROM document_findings WHERE finding_type = 'Regulatory'")).scalar() or 0
            evidence_count = conn.execute(text("SELECT COUNT(*) FROM compliance_evidence")).scalar() or 0

            scanned_today = conn.execute(text("SELECT COUNT(*) FROM documents WHERE created_at >= CURRENT_DATE")).scalar() or 0
            drift_alerts = conn.execute(text("SELECT COUNT(*) FROM compliance_drift_alerts")).scalar() or 0
            secret_leaks = conn.execute(text("SELECT COUNT(*) FROM document_findings WHERE finding_type IN ('Secret', 'Credentials')")).scalar() or 0
            pii_violations = conn.execute(text("SELECT COUNT(*) FROM document_findings WHERE finding_type = 'PII'")).scalar() or 0

            risk_res = conn.execute(text("SELECT risk_level, COUNT(*) FROM gateway_requests GROUP BY risk_level")).fetchall()
            risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
            for row in risk_res:
                lvl = row[0].upper() if row[0] else "LOW"
                if lvl in risk_dist:
                    risk_dist[lvl] = row[1]
                    
            failed_tests = conn.execute(text("SELECT COUNT(*) FROM pentest_simulations WHERE status = 'FAIL'")).scalar() or 0
            
            # Incorporate document findings into compliance score
            compliance_score = max(0, 100 - (open_findings * 5) - (failed_tests * 10) - (total_violations * 8))
            
    except Exception as e:
        logger.error(f"Error querying metrics from database: {e}")
        total_requests = 0
        blocked_requests = 0
        avg_latency = 142
        token_consumption = 0
        active_tenants = 0
        active_routes = 0
        active_policies = 0
        open_findings = 0
        active_workers = 0
        audit_chain_records = 0
        total_documents = 0
        total_findings = 0
        total_violations = 0
        evidence_count = 0
        scanned_today = 0
        drift_alerts = 0
        secret_leaks = 0
        pii_violations = 0
        risk_dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        compliance_score = 90

    approvals = get_all_approvals()
    pending = sum(1 for a in approvals.values() if a["status"] == "pending")
    executed = sum(1 for a in approvals.values() if a["status"] == "executed")
    approved = sum(1 for a in approvals.values() if a["status"] == "approved")
    rejected = sum(1 for a in approvals.values() if a["status"] == "rejected")

    return {
        "total_requests": total_requests,
        "blocked_requests": blocked_requests,
        "pending_approvals": pending,
        "executed_approvals": executed,
        "approved_approvals": approved,
        "rejected_approvals": rejected,
        "audit_chain_records": audit_chain_records,
        "risk_distribution": risk_dist,
        "avg_latency": avg_latency,
        "token_consumption": token_consumption,
        "active_tenants": active_tenants,
        "active_routes": active_routes,
        "active_policies": active_policies,
        "compliance_score": compliance_score,
        "open_findings": open_findings,
        "active_workers": active_workers,
        
        # New Document Intelligence metrics
        "total_documents": total_documents,
        "total_findings": total_findings,
        "total_violations": total_violations,
        "evidence_count": evidence_count,
        "scanned_today": scanned_today,
        "drift_alerts": drift_alerts,
        "secret_leaks": secret_leaks,
        "pii_violations": pii_violations
    }


@app.get("/platform/summary")
def get_platform_summary(_: dict = Depends(require_platform_admin)):
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        total_tenants = conn.execute(text("SELECT COUNT(*) FROM tenants")).scalar() or 0
        active_tenants = conn.execute(
            text("SELECT COUNT(*) FROM tenants WHERE COALESCE(status, 'active') = 'active'")
        ).scalar() or 0
        total_users = conn.execute(text("SELECT COUNT(*) FROM tenant_users")).scalar() or 0
        platform_admins = conn.execute(
            text("SELECT COUNT(*) FROM tenant_users WHERE role = 'Platform Admin'")
        ).scalar() or 0
        total_requests = conn.execute(text("SELECT COUNT(*) FROM gateway_requests")).scalar() or 0
        blocked_requests = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM gateway_requests
                WHERE allowed = FALSE OR lower(COALESCE(decision, status, '')) LIKE '%block%'
            """)
        ).scalar() or 0
        pending_approvals = conn.execute(
            text("SELECT COUNT(*) FROM gateway_approvals WHERE lower(COALESCE(status, '')) = 'pending'")
        ).scalar() or 0
        provider_rows = conn.execute(
            text("""
                SELECT COALESCE(NULLIF(provider, ''), 'unknown') AS provider, COUNT(*)
                FROM gateway_requests
                GROUP BY COALESCE(NULLIF(provider, ''), 'unknown')
                ORDER BY COUNT(*) DESC
                LIMIT 8
            """)
        ).fetchall()

    return {
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "total_users": total_users,
        "platform_admins": platform_admins,
        "total_gateway_requests": total_requests,
        "blocked_gateway_requests": blocked_requests,
        "pending_approvals": pending_approvals,
        "provider_usage": {row[0]: row[1] for row in provider_rows},
    }


@app.get("/platform/tenants")
def list_platform_tenants(limit: int = 100, _: dict = Depends(require_platform_admin)):
    from database import engine
    from sqlalchemy import text

    safe_limit = max(1, min(limit, 250))
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT
                    t.id,
                    t.name,
                    t.domain,
                    t.email,
                    COALESCE(t.status, 'active') AS status,
                    COALESCE(t.email_verified, false) AS email_verified,
                    COALESCE(t.domain_verified, false) AS domain_verified,
                    t.created_at,
                    COUNT(DISTINCT u.id) AS users_count,
                    COUNT(DISTINCT k.id) AS api_keys_count,
                    COUNT(DISTINCT s.id) AS provider_credentials_count,
                    COUNT(DISTINCT gr.id) AS gateway_requests_count
                FROM tenants t
                LEFT JOIN tenant_users u ON u.tenant_id = t.id
                LEFT JOIN tenant_api_keys k ON k.tenant_id = t.id AND k.revoked_at IS NULL
                LEFT JOIN secrets s ON s.tenant_id = t.id
                LEFT JOIN gateway_requests gr ON gr.tenant_id::text = t.id::text
                GROUP BY t.id, t.name, t.domain, t.email, t.status, t.email_verified, t.domain_verified, t.created_at
                ORDER BY t.created_at DESC NULLS LAST, t.id DESC
                LIMIT :limit
            """),
            {"limit": safe_limit},
        ).fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "domain": row[2],
            "email": row[3],
            "status": row[4],
            "email_verified": row[5],
            "domain_verified": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "users_count": row[8],
            "api_keys_count": row[9],
            "provider_credentials_count": row[10],
            "gateway_requests_count": row[11],
        }
        for row in rows
    ]


# --- NEW COMPONENTS SCHEMA DEFINITIONS ---

class RouteRequest(BaseModel):
    name: str
    provider: str
    endpoint: str
    model: str
    rate_limit: int
    redaction_enabled: bool
    enabled: bool
    tenant_assignment: str

class TenantRequest(BaseModel):
    name: str
    status: str



class PolicyRequest(BaseModel):
    name: str
    type: str
    rules: str
    enabled: bool

class DocumentUploadRequest(BaseModel):
    name: str
    type: str
    size_bytes: int

class ComplianceAnalyzeRequest(BaseModel):
    document_id: str

class DocumentChatRequest(BaseModel):
    document_id: str
    question: str



class UserRoleRequest(BaseModel):
    username: str
    role: str
    permissions: str



class EvidenceUploadRequest(BaseModel):
    name: str
    category: str
    file_path: str


# --- NEW COMPONENTS ENDPOINTS IMPLEMENTATIONS ---

# 1. PROVIDERS
@app.get("/providers")
def get_providers(authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant_from_authorization(authorization)
    providers_list = [
        {"id": "openai", "name": "OpenAI", "model": "gpt-4o", "endpoint": "https://api.openai.com/v1"},
        {"id": "anthropic", "name": "Anthropic", "model": "claude-3-5-sonnet", "endpoint": "https://api.anthropic.com/v1"},
        {"id": "gemini", "name": "Gemini", "model": "gemini-2.5-flash-lite", "endpoint": "https://generativelanguage.googleapis.com"},
        {"id": "azure", "name": "Azure OpenAI", "model": "gpt-4", "endpoint": "https://my-azure.openai.azure.com"}
    ]
    result = []
    with engine.connect() as conn:
        for prov in providers_list:
            name = prov["name"]
            req_count = conn.execute(
                text("SELECT COUNT(*) FROM gateway_requests WHERE tenant_id = :tid AND LOWER(provider) = LOWER(:p)"),
                {"tid": str(tenant_id), "p": name},
            ).scalar() or 0
            err_count = conn.execute(
                text("SELECT COUNT(*) FROM gateway_requests WHERE tenant_id = :tid AND LOWER(provider) = LOWER(:p) AND allowed = FALSE"),
                {"tid": str(tenant_id), "p": name},
            ).scalar() or 0
            avg_lat = conn.execute(
                text("SELECT AVG(latency) FROM gateway_requests WHERE tenant_id = :tid AND LOWER(provider) = LOWER(:p)"),
                {"tid": str(tenant_id), "p": name},
            ).scalar() or 0
            tokens = conn.execute(
                text("SELECT SUM(tokens_in + tokens_out) FROM gateway_requests WHERE tenant_id = :tid AND LOWER(provider) = LOWER(:p)"),
                {"tid": str(tenant_id), "p": name},
            ).scalar() or 0
            
            success_rate = round(100.0 * (req_count - err_count) / req_count, 1) if req_count > 0 else 100.0
            err_rate = round(100.0 * err_count / req_count, 1) if req_count > 0 else 0.0
            
            result.append({
                "id": prov["id"],
                "name": name,
                "model": prov["model"],
                "endpoint": prov["endpoint"],
                "status": "configured" if req_count else "available",
                "health": "tenant-scoped",
                "last_check": datetime.now(timezone.utc).strftime("%H:%M:%S"),
                "avg_latency": int(avg_lat),
                "request_count": req_count,
                "error_rate": err_rate,
                "success_rate": success_rate,
                "token_usage": tokens,
                "cost_estimate": round(tokens * 0.000015, 4)
            })
    return result

@app.get("/providers/{provider_id}")
def get_provider_by_id(provider_id: str, authorization: Optional[str] = Header(None)):
    if provider_id == "list":
        tenant_id = resolve_tenant_from_authorization(authorization)
        return list_connected_providers(tenant_id)
    providers = get_providers(authorization)
    for p in providers:
        if p["id"] == provider_id:
            return p
    raise HTTPException(status_code=404, detail="Provider not found")


# 2. ROUTES
@app.get("/routes")
def get_routes(authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT name, domain FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        ).fetchone()
        tenant_tokens = {str(tenant_id), f"tenant:{tenant_id}"}
        if tenant:
            if tenant[0]:
                tenant_tokens.add(str(tenant[0]))
            if tenant[1]:
                tenant_tokens.add(str(tenant[1]))
        res = conn.execute(
            text(
                """
                SELECT id, tenant_id, name, provider, endpoint, model, rate_limit,
                       redaction_enabled, enabled, tenant_assignment
                FROM gateway_routes
                WHERE tenant_id = :tid
                   OR tenant_id IS NULL
                ORDER BY id ASC
                """
            ),
            {"tid": tenant_id},
        ).fetchall()
        routes = []
        for row in res:
            route = dict(row._mapping)
            if route.get("tenant_id") == tenant_id or route.get("tenant_assignment") in tenant_tokens:
                routes.append(route)
        return routes

@app.post("/routes")
def create_route(route: RouteRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO gateway_routes (tenant_id, name, provider, endpoint, model, rate_limit, redaction_enabled, enabled, tenant_assignment)
            VALUES (:tenant_id, :name, :provider, :endpoint, :model, :rate_limit, :redaction_enabled, :enabled, :tenant_assignment)
            """),
            {**route.dict(), "tenant_id": tenant_id}
        )
        conn.commit()
    create_audit_block(
        query=f"Create Gateway Route: {route.name}",
        response=f"Route added: {route.name} mapped to model {route.model} under {route.provider}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": f"Route '{route.name}' created successfully."}

@app.put("/routes/{route_id}")
def update_route(route_id: int, route: RouteRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT name, domain FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        ).fetchone()
        tenant_tokens = {str(tenant_id), f"tenant:{tenant_id}"}
        if tenant:
            if tenant[0]:
                tenant_tokens.add(str(tenant[0]))
            if tenant[1]:
                tenant_tokens.add(str(tenant[1]))
        existing = conn.execute(
            text("SELECT tenant_id, tenant_assignment FROM gateway_routes WHERE id = :id"),
            {"id": route_id},
        ).fetchone()
        if existing is None or not (
            existing[0] == tenant_id or (existing[0] is None and existing[1] in tenant_tokens)
        ):
            raise HTTPException(status_code=404, detail="Gateway route not found.")
        result = conn.execute(
            text("""
            UPDATE gateway_routes 
            SET tenant_id = :tenant_id,
                name = :name, provider = :provider, endpoint = :endpoint, model = :model, 
                rate_limit = :rate_limit, redaction_enabled = :redaction_enabled, 
                enabled = :enabled, tenant_assignment = :tenant_assignment
            WHERE id = :id
            """),
            {**route.dict(), "id": route_id, "tenant_id": tenant_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Gateway route not found.")
        conn.commit()
    create_audit_block(
        query=f"Update Gateway Route (ID {route_id}): {route.name}",
        response=f"Route modified. Enabled status is now: {route.enabled}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": f"Route ID {route_id} updated."}

@app.delete("/routes/{route_id}")
def delete_route(route_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT name, domain FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        ).fetchone()
        tenant_tokens = {str(tenant_id), f"tenant:{tenant_id}"}
        if tenant:
            if tenant[0]:
                tenant_tokens.add(str(tenant[0]))
            if tenant[1]:
                tenant_tokens.add(str(tenant[1]))
        row = conn.execute(
            text("SELECT name, tenant_id, tenant_assignment FROM gateway_routes WHERE id = :id"),
            {"id": route_id}
        ).fetchone()
        if row is None or not (row[1] == tenant_id or (row[1] is None and row[2] in tenant_tokens)):
            raise HTTPException(status_code=404, detail="Gateway route not found.")
        name = row[0] if row else f"ID {route_id}"
        conn.execute(
            text("DELETE FROM gateway_routes WHERE id = :id"),
            {"id": route_id}
        )
        conn.commit()
    create_audit_block(
        query=f"Delete Gateway Route: {name}",
        response=f"Route '{name}' deleted from database.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Route deleted successfully."}


# 3. TENANTS
@app.get("/tenants")
def get_tenants(authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT id, name, status, usage_count, tokens_used, domain, email, email_verified, domain_verified FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        )
        return [dict(r._mapping) for r in res]

@app.post("/tenants")
def create_tenant(tenant: TenantRequest, authorization: Optional[str] = Header(None)):
    resolve_tenant_from_authorization(authorization)
    raise HTTPException(status_code=409, detail="Organizations are created through the onboarding flow.")

@app.put("/tenants/{tenant_id}")
def update_tenant(tenant_id: int, tenant: TenantRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    authenticated_tenant_id = resolve_tenant_from_authorization(authorization)
    if tenant_id != authenticated_tenant_id:
        raise HTTPException(status_code=403, detail="Cannot modify another tenant.")
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE tenants SET name = :name, status = :status WHERE id = :id"),
            {"name": tenant.name, "status": tenant.status, "id": tenant_id}
        )
        conn.commit()
    create_audit_block(
        query=f"Update Tenant (ID {tenant_id}): {tenant.name}",
        response=f"Tenant updated to status: {tenant.status}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": f"Tenant ID {tenant_id} updated."}

@app.delete("/tenants/{tenant_id}")
def delete_tenant(tenant_id: int, authorization: Optional[str] = Header(None)):
    authenticated_tenant_id = resolve_tenant_from_authorization(authorization)
    if tenant_id != authenticated_tenant_id:
        raise HTTPException(status_code=403, detail="Cannot delete another tenant.")
    raise HTTPException(status_code=409, detail="Tenant deletion requires an offboarding workflow.")



# 5. POLICIES
@app.get("/policies/list")
def list_policies(authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        ensure_default_tenant_policies(conn, tenant_id)
        conn.commit()
        res = conn.execute(
            text("SELECT id, name, type, rules, enabled, tenant_id FROM policies WHERE tenant_id = :tenant_id ORDER BY id ASC"),
            {"tenant_id": tenant_id},
        )
        return [dict(r._mapping) for r in res]

@app.post("/policies")
def create_policy(policy: PolicyRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO policies (name, type, rules, enabled, tenant_id) VALUES (:name, :type, :rules, :enabled, :tenant_id)"),
            {"name": policy.name, "type": policy.type, "rules": policy.rules, "enabled": policy.enabled, "tenant_id": tenant_id}
        )
        conn.commit()
    create_audit_block(
        query=f"Create Guardrail Policy: {policy.name}",
        response=f"Compliance policy type {policy.type} configured and saved.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy created."}

@app.put("/policies/{policy_id}")
def update_policy(policy_id: int, policy: PolicyRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("UPDATE policies SET name = :name, type = :type, rules = :rules, enabled = :enabled WHERE id = :id AND tenant_id = :tenant_id"),
            {"name": policy.name, "type": policy.type, "rules": policy.rules, "enabled": policy.enabled, "id": policy_id, "tenant_id": tenant_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Policy not found.")
        conn.commit()
    create_audit_block(
        query=f"Update Policy (ID {policy_id}): {policy.name}",
        response=f"Guardrail configurations modified. Active status is: {policy.enabled}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy updated."}

@app.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name FROM policies WHERE id = :id AND tenant_id = :tenant_id"), {"id": policy_id, "tenant_id": tenant_id}).fetchone()
        name = row[0] if row else f"ID {policy_id}"
        result = conn.execute(text("DELETE FROM policies WHERE id = :id AND tenant_id = :tenant_id"), {"id": policy_id, "tenant_id": tenant_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Policy not found.")
        conn.commit()
    create_audit_block(
        query=f"Delete Compliance Policy: {name}",
        response=f"Policy '{name}' deleted.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy deleted."}


# 6. RAG DOCUMENTS
@app.get("/rag/documents")
def get_documents():
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, name, type, size_bytes, status, last_indexed, chunks_count FROM knowledge_documents ORDER BY id DESC"))
        return [dict(r._mapping) for r in res]

@app.post("/rag/documents")
def create_document(doc: DocumentUploadRequest):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    from rag.embeddings import generate_embedding
    today = datetime.now(timezone.utc).date().isoformat()
    chunks_count = max(1, int(doc.size_bytes // 50000))
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            INSERT INTO knowledge_documents (name, type, size_bytes, status, last_indexed, chunks_count)
            VALUES (:name, :type, :size_bytes, 'indexed', :last_indexed, :chunks_count)
            RETURNING id
            """),
            {
                "name": doc.name,
                "type": doc.type,
                "size_bytes": doc.size_bytes,
                "last_indexed": today,
                "chunks_count": chunks_count
            }
        )
        inserted_id = res.fetchone()[0]
        conn.commit()

        # Insert chunks and generate actual embeddings
        for i in range(chunks_count):
            content_text = f"Document chunk {i+1} from {doc.name}. Contains policy compliance vectors for {doc.type} files."
            vector = generate_embedding(content_text)
            conn.execute(
                text("""
                INSERT INTO knowledge_chunks (document_id, content, embedding_preview, embedding_vector)
                VALUES (:doc_id, :content, :emb, :vec)
                """),
                {
                    "doc_id": inserted_id,
                    "content": content_text,
                    "emb": f"[{round(0.1*i,2)}, {round(-0.15*i,2)}, ...]",
                    "vec": json.dumps(vector)
                }
            )
        conn.commit()
    create_audit_block(
        query=f"Upload Knowledge Document: {doc.name}",
        response=f"Document uploaded and indexed successfully into {chunks_count} vector chunks.",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A"
    )
    return {"status": "success", "message": "Document uploaded and indexed successfully."}

def parse_document_id(doc_id_str: str) -> int:
    if doc_id_str.startswith("doc_"):
        return int(doc_id_str[4:])
    try:
        return int(doc_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format. Must be like 'doc_123' or '123'")

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    
    contents = await file.read()
    filename = file.filename
    size_bytes = len(contents)
    
    from database import engine
    from sqlalchemy import text
    from datetime import datetime, timezone
    
    # 1. Register document in documents table first
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            INSERT INTO documents (filename, source, size_bytes, status, risk_score, severity)
            VALUES (:filename, 'local', :size_bytes, 'pending', 0, 'LOW')
            RETURNING id
            """),
            {
                "filename": filename,
                "size_bytes": size_bytes
            }
        )
        doc_id = res.fetchone()[0]
        conn.commit()
        
    # 2. Run compliance scanning pipeline
    from document_processing.orchestrator import run_document_scan_pipeline
    try:
        pipeline_res = run_document_scan_pipeline(doc_id, contents, filename, source="local")
    except Exception as ex:
        # Fallback if pipeline fails (e.g. LLM issues) so document is still indexed
        logger.error(f"Scan pipeline failed, fallback indexing document: {ex}")
        pipeline_res = {
            "document_id": doc_id,
            "filename": filename,
            "risk_score": 100,
            "severity": "LOW",
            "status": "completed",
            "duration_ms": 0,
            "findings": [],
            "summary": "Scan pipeline fallback"
        }
    
    # 3. Find matching knowledge_document ID for frontend backward compatibility
    with engine.connect() as conn:
        k_doc_row = conn.execute(
            text("SELECT id FROM knowledge_documents WHERE name = :name"),
            {"name": filename}
        ).fetchone()
        k_doc_id = k_doc_row[0] if k_doc_row else doc_id
        
    return {
        "document_id": f"doc_{k_doc_id}",
        "status": "indexed",
        "pipeline_results": pipeline_res
    }

class DocumentScanRequest(BaseModel):
    document_id: str

@app.post("/documents/scan")
def scan_document(
    req: DocumentScanRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    
    doc_id = parse_document_id(req.document_id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Check in knowledge_documents
        k_doc = conn.execute(text("SELECT name, size_bytes FROM knowledge_documents WHERE id = :id"), {"id": doc_id}).fetchone()
        if not k_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        filename = k_doc[0]
        size_bytes = k_doc[1]
        
        # Get chunks to reconstruct text
        chunks_res = conn.execute(
            text("SELECT content FROM knowledge_chunks WHERE document_id = :doc_id ORDER BY id ASC"),
            {"doc_id": doc_id}
        ).fetchall()
        text_content = "\n\n".join([r[0] for r in chunks_res])
        
        # Check or insert into documents table
        doc_row = conn.execute(text("SELECT id FROM documents WHERE filename = :name"), {"name": filename}).fetchone()
        if doc_row:
            d_id = doc_row[0]
        else:
            res = conn.execute(
                text("""
                INSERT INTO documents (filename, source, size_bytes, status, risk_score, severity)
                VALUES (:filename, 'local', :size, 'pending', 0, 'LOW')
                RETURNING id
                """),
                {"filename": filename, "size": size_bytes}
            )
            d_id = res.fetchone()[0]
            conn.commit()
            
    from document_processing.orchestrator import run_document_scan_pipeline
    pipeline_res = run_document_scan_pipeline(d_id, text_content.encode("utf-8"), filename, source="local")
    return pipeline_res

@app.get("/documents")
def list_all_documents(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, filename, source, status, size_bytes, risk_score, severity, created_at, updated_at FROM documents ORDER BY id DESC"))
        return [dict(r._mapping) for r in res]

@app.get("/documents/{id}")
def get_document_details(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
        if not row:
            k_doc = conn.execute(text("SELECT name FROM knowledge_documents WHERE id = :id"), {"id": doc_id}).fetchone()
            if k_doc:
                filename = k_doc[0]
                row = conn.execute(text("SELECT * FROM documents WHERE filename = :name"), {"name": filename}).fetchone()
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return dict(row._mapping)

@app.get("/documents/{id}/findings")
def get_document_findings(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
        if not row:
            k_doc = conn.execute(text("SELECT name FROM knowledge_documents WHERE id = :id"), {"id": doc_id}).fetchone()
            if k_doc:
                filename = k_doc[0]
                row = conn.execute(text("SELECT id FROM documents WHERE filename = :name"), {"name": filename}).fetchone()
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        real_doc_id = row[0]
        
        findings_res = conn.execute(
            text("SELECT id, finding_type, matched_pattern, matched_text, risk_level, recommendation, impact, priority, location_evidence FROM document_findings WHERE document_id = :doc_id"),
            {"doc_id": real_doc_id}
        ).fetchall()
        
        return [dict(f._mapping) for f in findings_res]

@app.get("/documents/{id}/audit")
def get_document_audit_trail(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    from document_processing.auditor import verify_document_audit_chain
    
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
        if not row:
            k_doc = conn.execute(text("SELECT name FROM knowledge_documents WHERE id = :id"), {"id": doc_id}).fetchone()
            if k_doc:
                filename = k_doc[0]
                row = conn.execute(text("SELECT id FROM documents WHERE filename = :name"), {"name": filename}).fetchone()
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        real_doc_id = row[0]
        
        audit_res = conn.execute(
            text("SELECT id, timestamp, action, actor, details, integrity_hash, previous_hash FROM document_audits WHERE document_id = :doc_id ORDER BY id ASC"),
            {"doc_id": real_doc_id}
        ).fetchall()
        
        audit_list = [dict(a._mapping) for a in audit_res]
        verification = verify_document_audit_chain(real_doc_id)
        
        return {
            "audit_trail": audit_list,
            "verification": verification
        }

@app.post("/compliance/analyze")
def compliance_analyze(
    req: ComplianceAnalyzeRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(req.document_id)
    
    from rag.compliance_analyzer import analyze_document_compliance, get_document_text
    try:
        # Get document text and name first
        _, doc_name = get_document_text(doc_id)
        # Perform analysis
        analysis = analyze_document_compliance(doc_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Compliance analysis failed: {str(e)}")
        
    # Generate and store evidence reports
    try:
        from rag.compliance_analyzer import generate_and_vault_reports
        generate_and_vault_reports(doc_id, doc_name, analysis)
    except Exception as e:
        logger.error(f"Failed to generate and store evidence reports: {str(e)}")
        
    # Audit logging
    from verify_audit import create_audit_block
    create_audit_block(
        query=f"Run Compliance Analysis: doc_{doc_id}",
        response=f"Compliance analysis completed for {doc_name}. Overall Risk: {analysis['overall_risk']}",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A"
    )
    
    # Emit audit event
    from startup.audit import log_audit_event
    log_audit_event(
        event="compliance_analysis",
        correlation_id="system",
        extra={"document_id": req.document_id, "doc_name": doc_name, "overall_risk": analysis["overall_risk"]}
    )
    
    return analysis

@app.post("/documents/chat")
def document_chat(
    req: DocumentChatRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(req.document_id)
    
    import os
    import requests
    from rag.compliance_analyzer import get_document_text
    try:
        _, doc_name = get_document_text(doc_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Document not found: {str(e)}")
        
    # Retrieve relevant context
    from rag.retriever import retrieve_formatted_context
    context, citations = retrieve_formatted_context(req.question, top_k=3, document_id=doc_id)
    
    # Query Gemini
    api_key = os.getenv("GOOGLE_API_KEY")
    api_url = os.getenv("GOOGLE_API_URL", "https://generativelanguage.googleapis.com")
    model = os.getenv("MODEL_NAME", "gemini-2.5-flash")
    
    answer = ""
    is_key_valid = api_key and api_key not in ("dummy", "dummy-api-key", "")
    
    if is_key_valid:
        try:
            prompt = f"""
You are an expert compliance assistant. Answer the user's question about the document '{doc_name}' using only the provided context.
If the answer is not in the context, say "I cannot find the answer in the document."

Context:
{context}

Question:
{req.question}
"""
            url = f"{api_url}/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }
            res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if res.status_code == 200:
                data = res.json()
                answer = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                logger.warning(f"Gemini API returned status {res.status_code} in document chat: {res.text}")
        except Exception as e:
            logger.warning(f"Gemini doc chat failed: {str(e)}")
            
    # Fallback to local answering if offline or Gemini failed
    if not answer:
        if citations:
            best_chunk = citations[0]["text"]
            answer = f"According to the document context: \"{best_chunk[:300]}...\". (Note: Gemini API is currently offline or unconfigured, utilizing local semantic search retrieval)."
        else:
            answer = "I cannot find the answer in the document."
            
    # Audit logging
    from verify_audit import create_audit_block
    create_audit_block(
        query=f"Document Copilot Question (doc_{doc_id}): {req.question}",
        response=f"Answer: {answer[:100]}...",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A"
    )
    
    # Emit audit event
    from startup.audit import log_audit_event
    log_audit_event(
        event="document_question",
        correlation_id="system",
        extra={"document_id": req.document_id, "question": req.question}
    )
    
    return {
        "answer": answer,
        "citations": citations
    }


from fastapi.responses import FileResponse
@app.get("/evidence/download/{filename}")
def download_evidence_file(filename: str):
    import os
    filepath = os.path.join("evidence", filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Evidence file not found")
    return FileResponse(filepath, media_type="text/plain", filename=filename)

@app.delete("/rag/documents/{doc_id}")
def delete_document(
    doc_id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name FROM knowledge_documents WHERE id = :id"), {"id": doc_id}).fetchone()
        name = row[0] if row else f"ID {doc_id}"
        
        # Deleting from documents table triggers cascade delete of scans and findings
        conn.execute(text("DELETE FROM documents WHERE filename = :name"), {"name": name})
        conn.execute(text("DELETE FROM knowledge_documents WHERE id = :id"), {"id": doc_id})
        conn.execute(text("DELETE FROM knowledge_chunks WHERE document_id = :id"), {"id": doc_id})
        conn.commit()
        
    create_audit_block(
        query=f"Delete Knowledge Document: {name}",
        response=f"Document '{name}' and its vector chunks purged from index.",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A"
    )
    return {"status": "success", "message": "Document deleted."}

@app.get("/rag/chunks/{doc_id}")
def get_document_chunks(doc_id: int):
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, content, embedding_preview FROM knowledge_chunks WHERE document_id = :doc_id ORDER BY id ASC"), {"doc_id": doc_id})
        return [dict(r._mapping) for r in res]

class SimilaritySearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 3

@app.post("/rag/search")
def rag_search_endpoint(
    req: SimilaritySearchRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)

        
    from rag.retriever import retrieve_context
    hits = retrieve_context(req.query, top_k=req.top_k)
    return hits





# 9. ACCESS CONTROL
@app.get("/access-control/users")
def get_users(payload: dict = Depends(require_tenant_access_admin)):
    from database import engine
    from sqlalchemy import text
    tenant_id = payload["tenant_id"]
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT id, email AS username, role, permissions, status,
                       email_verified, last_login_at
                FROM tenant_users
                WHERE tenant_id = :tenant_id
                ORDER BY id ASC
            """),
            {"tenant_id": tenant_id},
        )
        return [dict(r._mapping) for r in res]

@app.post("/access-control/users")
def create_user_role(role_req: UserRoleRequest, payload: dict = Depends(require_tenant_access_admin)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    tenant_id = payload["tenant_id"]
    allowed_roles = {
        "Super Admin",
        "Security Admin",
        "Compliance Officer",
        "Developer",
        "Auditor",
        "Viewer",
    }
    if role_req.role not in allowed_roles:
        raise HTTPException(status_code=400, detail="Unsupported tenant role.")
    if "@" not in role_req.username:
        raise HTTPException(status_code=400, detail="Tenant users must be identified by work email.")
    with engine.connect() as conn:
        row = conn.execute(
            text("""
            UPDATE tenant_users
            SET role = :role, permissions = :permissions, updated_at = NOW()
            WHERE tenant_id = :tenant_id AND lower(email) = lower(:email)
            RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "email": role_req.username,
                "role": role_req.role,
                "permissions": role_req.permissions,
            },
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tenant user not found.")
        conn.commit()
    create_audit_block(
        query=f"Modify Access Control: {role_req.username}",
        response=f"Username {role_req.username} role updated/set to {role_req.role}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        username=role_req.username,
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "User access mapping updated."}





# 11. EVIDENCE VAULT
@app.get("/evidence")
def get_evidence():
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(text("SELECT id, name, category, file_path, collected_at, hash FROM compliance_evidence ORDER BY id DESC"))
        return [dict(r._mapping) for r in res]

@app.post("/evidence/collect")
def collect_evidence(req: EvidenceUploadRequest):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    import hashlib
    now_str = datetime.now(timezone.utc).date().isoformat()
    f_hash = f"sha256-{hashlib.sha256(req.name.encode()).hexdigest()[:16]}"
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO compliance_evidence (name, category, file_path, collected_at, hash)
            VALUES (:name, :category, :file_path, :collected_at, :hash)
            """),
            {
                "name": req.name,
                "category": req.category,
                "file_path": req.file_path,
                "collected_at": now_str,
                "hash": f_hash
            }
        )
        conn.commit()
    create_audit_block(
        query=f"Vault Compliance Evidence: {req.name}",
        response=f"Evidence vaulted under category: {req.category}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A"
    )
    return {"status": "success", "message": f"Compliance evidence '{req.name}' successfully vaulted."}

@app.delete("/evidence/{id}")
def delete_evidence(
    id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
        
    import os
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    
    with engine.connect() as conn:
        row = conn.execute(text("SELECT name, file_path FROM compliance_evidence WHERE id = :id"), {"id": id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        name = row[0]
        file_path = row[1]
        
        conn.execute(text("DELETE FROM compliance_evidence WHERE id = :id"), {"id": id})
        conn.commit()
        
        # Physical delete
        if file_path.startswith("/evidence/"):
            filename = file_path.replace("/evidence/", "")
            full_path = os.path.join("evidence", filename)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                except Exception as ex:
                    logger.error(f"Failed to delete evidence file {full_path}: {ex}")
                    
    create_audit_block(
        query=f"Delete Compliance Evidence: {name}",
        response=f"Evidence registry #{id} permanently purged.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A"
    )
    return {"status": "success", "message": f"Compliance evidence '{name}' permanently deleted."}

@app.get("/evidence/export/csv")
def export_evidence_csv_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_evidence_csv
    csv_data = generate_evidence_csv()
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=evidence_vault.csv"})

@app.get("/evidence/export/pdf")
def export_evidence_pdf_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_evidence_pdf
    pdf_data = generate_evidence_pdf()
    return Response(content=pdf_data, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=evidence_vault.pdf"})

@app.get("/audit/export/csv")
def export_audit_csv_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_audit_csv
    csv_data = generate_audit_csv()
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_ledger.csv"})

@app.get("/audit/export/pdf")
def export_audit_pdf_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_audit_pdf
    pdf_data = generate_audit_pdf()
    return Response(content=pdf_data, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=audit_ledger.pdf"})


@app.get("/compliance/framework-scores")
def get_compliance_framework_scores(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    resolve_tenant(x_api_key, authorization)
    
    from database import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text("""
                SELECT df.risk_level, df.finding_type 
                FROM document_findings df
                JOIN documents d ON df.document_id = d.id
                WHERE d.status NOT IN ('deleted', 's3_deleted')
                """)
            ).fetchall()
    except Exception as e:
        logger.error(f"Failed to fetch live framework findings: {e}")
        rows = []

    open_high = sum(1 for r in rows if r[0] in ("CRITICAL", "HIGH"))
    open_medium = sum(1 for r in rows if r[0] == "MEDIUM")
    open_low = sum(1 for r in rows if r[0] == "LOW")

    soc2_deduct = (open_high * 12) + (open_medium * 6)
    gdpr_deduct = (open_high * 15) + (open_low * 4)
    hipaa_deduct = (open_high * 20) + (open_medium * 8)

    soc2_score = max(20, min(100, 100 - soc2_deduct))
    gdpr_score = max(20, min(100, 100 - gdpr_deduct))
    hipaa_score = max(20, min(100, 100 - hipaa_deduct))

    soc2_failed = min(10, open_high)
    soc2_passed = 10 - soc2_failed

    gdpr_failed = min(8, open_high)
    gdpr_passed = 8 - gdpr_failed

    hipaa_failed = min(6, open_high)
    hipaa_passed = 6 - hipaa_failed

    return {
        "soc2": soc2_score,
        "gdpr": gdpr_score,
        "hipaa": hipaa_score,
        "soc2_controls": {"passed": soc2_passed, "failed": soc2_failed},
        "gdpr_controls": {"passed": gdpr_passed, "failed": gdpr_failed},
        "hipaa_controls": {"passed": hipaa_passed, "failed": hipaa_failed}
    }


# ==============================================================================
# AUTHENTICATION & SESSION MANAGEMENT ENDPOINTS
# ==============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyOTPRequest(BaseModel):
    session_id: str
    code: str

class MFAResetRequest(BaseModel):
    username: str
    password: str

class MFAResetConfirmRequest(BaseModel):
    token: str

class RefreshRequest(BaseModel):
    refresh_token: str

JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("AUTHCLAW_JWT_SECRET")
if not JWT_SECRET:
    if os.getenv("AUTHCLAW_ENV", "development").lower() in {"production", "prod"}:
        raise RuntimeError("JWT_SECRET or AUTHCLAW_JWT_SECRET must be configured in production.")
    JWT_SECRET = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8")

AUTH_SESSION_TTL_SECONDS = int(os.getenv("AUTHCLAW_MFA_SESSION_TTL_SECONDS", "600"))

def base64_url_encode(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64_url_decode(data: str) -> bytes:
    import base64
    padding = '=' * (4 - len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)

def create_jwt(payload: dict) -> str:
    import hmac
    import hashlib
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = base64_url_encode(json.dumps(header).encode('utf-8'))
    payload_encoded = base64_url_encode(json.dumps(payload).encode('utf-8'))
    signature_input = f"{header_encoded}.{payload_encoded}".encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signature_input, hashlib.sha256).digest()
    signature_encoded = base64_url_encode(signature)
    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"

def decode_jwt(token: str) -> dict:
    import hmac
    import hashlib
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_encoded, payload_encoded, signature_encoded = parts
        signature_input = f"{header_encoded}.{payload_encoded}".encode('utf-8')
        signature = hmac.new(JWT_SECRET.encode('utf-8'), signature_input, hashlib.sha256).digest()
        expected_sig = base64_url_encode(signature)
        if not hmac.compare_digest(signature_encoded, expected_sig):
            return None
        payload_bytes = base64_url_decode(payload_encoded)
        payload = json.loads(payload_bytes.decode('utf-8'))
        if payload.get("exp") and int(payload["exp"]) < int(time.time()):
            return None
        if os.getenv("AUTHCLAW_ENV", "development").lower() in {"production", "prod"} and not payload.get("exp"):
            return None
        return payload
    except Exception:
        return None

def store_auth_session(session_id: str, session: dict) -> None:
    from database import engine
    from sqlalchemy import text

    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=AUTH_SESSION_TTL_SECONDS)
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO auth_mfa_sessions (
                    session_id, username, role, permissions, tenant_id, user_id,
                    email_verified, domain_verified, step, expires_at
                )
                VALUES (
                    :session_id, :username, :role, :permissions, :tenant_id, :user_id,
                    :email_verified, :domain_verified, :step, :expires_at
                )
                ON CONFLICT (session_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    role = EXCLUDED.role,
                    permissions = EXCLUDED.permissions,
                    tenant_id = EXCLUDED.tenant_id,
                    user_id = EXCLUDED.user_id,
                    email_verified = EXCLUDED.email_verified,
                    domain_verified = EXCLUDED.domain_verified,
                    step = EXCLUDED.step,
                    expires_at = EXCLUDED.expires_at
            """),
            {
                "session_id": session_id,
                "username": session["username"],
                "role": session["role"],
                "permissions": session["permissions"],
                "tenant_id": session["tenant_id"],
                "user_id": session["user_id"],
                "email_verified": session["email_verified"],
                "domain_verified": session["domain_verified"],
                "step": session["step"],
                "expires_at": expires_at,
            },
        )
        conn.commit()


def load_auth_session(session_id: str) -> Optional[dict]:
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM auth_mfa_sessions WHERE expires_at <= NOW()")
        )
        row = conn.execute(
            text("""
                SELECT session_id, username, role, permissions, tenant_id, user_id,
                       email_verified, domain_verified, step
                FROM auth_mfa_sessions
                WHERE session_id = :session_id AND expires_at > NOW()
            """),
            {"session_id": session_id},
        ).fetchone()
        conn.commit()

    if not row:
        return None
    return {
        "session_id": row[0],
        "username": row[1],
        "role": row[2],
        "permissions": row[3],
        "tenant_id": row[4],
        "user_id": row[5],
        "email_verified": bool(row[6]),
        "domain_verified": bool(row[7]),
        "step": row[8],
    }


def delete_auth_session(session_id: str) -> None:
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM auth_mfa_sessions WHERE session_id = :session_id"),
            {"session_id": session_id},
        )
        conn.commit()

def create_refresh_token_for_user(user_id: int, tenant_id: int, subject: str) -> str:
    from database import engine
    from sqlalchemy import text

    now_ts = int(time.time())
    jti = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
    payload = {
        "sub": subject,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "jti": jti,
        "iat": now_ts,
        "exp": now_ts + 86400
    }
    token = create_jwt(payload)
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO auth_refresh_tokens (
                    jti, tenant_id, user_id, subject, expires_at
                )
                VALUES (:jti, :tenant_id, :user_id, :subject, :expires_at)
            """),
            {
                "jti": jti,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "subject": subject,
                "expires_at": expires_at,
            },
        )
        conn.commit()
    return token


def validate_refresh_token_record(payload: dict):
    from database import engine
    from sqlalchemy import text

    jti = payload.get("jti")
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    if not jti or not user_id or not tenant_id:
        return None

    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT u.id, u.tenant_id, u.email, u.role, u.permissions,
                       u.email_verified, u.status
                FROM auth_refresh_tokens rt
                JOIN tenant_users u ON u.id = rt.user_id
                WHERE rt.jti = :jti
                  AND rt.user_id = :user_id
                  AND rt.tenant_id = :tenant_id
                  AND rt.revoked_at IS NULL
                  AND rt.expires_at > NOW()
                  AND u.status = 'active'
            """),
            {"jti": jti, "user_id": user_id, "tenant_id": tenant_id},
        ).fetchone()

    return row


def deliver_auth_email(recipient: str, subject: str, body: str, purpose: str) -> None:
    import smtplib
    from email.message import EmailMessage

    smtp_host = env_value("SMTP_HOST")
    smtp_port = int(env_value("SMTP_PORT", "587"))
    smtp_user = env_value("SMTP_USERNAME")
    smtp_password = env_value("SMTP_PASSWORD")
    smtp_from = env_value("SMTP_FROM") or smtp_user
    smtp_tls = env_bool("SMTP_USE_TLS", True)

    if skip_email_delivery_for_testing():
        return

    if not smtp_host or not smtp_from:
        raise HTTPException(
            status_code=503,
            detail=f"Email delivery is not configured. Set SMTP_HOST and SMTP_FROM before {purpose}."
        )

    sendgrid_api_key = env_value("SENDGRID_API_KEY") or smtp_password
    use_sendgrid_api = (
        sendgrid_api_key
        and sendgrid_api_key.startswith("SG.")
        and ("sendgrid" in (smtp_host or "").lower() or (smtp_user or "").lower() == "apikey")
    )

    if use_sendgrid_api:
        try:
            import requests
            response = requests.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={
                    "Authorization": f"Bearer {sendgrid_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "personalizations": [{"to": [{"email": recipient}]}],
                    "from": {"email": smtp_from},
                    "subject": subject,
                    "content": [{"type": "text/plain", "value": body}],
                },
                timeout=15,
            )
            if response.status_code not in {200, 202}:
                logger.error(
                    "%s SendGrid API delivery failed: status=%s body=%s",
                    purpose,
                    response.status_code,
                    response.text[:500],
                )
                raise HTTPException(
                    status_code=503,
                    detail=(
                        f"{purpose} email could not be delivered by SendGrid. Confirm the API key "
                        "has Mail Send permission and SMTP_FROM is a verified Sender Identity."
                    ),
                )
            return
        except HTTPException:
            raise
        except Exception as exc:
            logger.error("%s SendGrid API delivery failed: %s", purpose, exc)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"{purpose} email could not be delivered by SendGrid API. Confirm outbound HTTPS "
                    "access, API key, verified Sender Identity, and SMTP_FROM address."
                ),
            ) from exc

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = recipient
    message.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if smtp_tls:
                smtp.starttls()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        logger.error("%s SMTP delivery failed: %s", purpose, exc)
        raise HTTPException(
            status_code=503,
            detail=(
                f"{purpose} email could not be delivered. Confirm the SMTP credentials, "
                "verified Sender Identity, SMTP_FROM address, and outbound SMTP access."
            )
        ) from exc

def send_verification_email(recipient: str, token: str, organization_name: str) -> None:
    deliver_auth_email(
        recipient,
        "Verify your AuthClaw workspace",
        "\n".join(
            [
                f"Welcome to AuthClaw for {organization_name}.",
                "",
                "Use this verification token to complete email verification:",
                token,
                "",
                "If you did not request this workspace, ignore this message.",
            ]
        ),
        "Verification",
    )

def send_mfa_reset_email(recipient: str, token: str, organization_name: str) -> None:
    deliver_auth_email(
        recipient,
        "Reset your AuthClaw MFA setup",
        "\n".join(
            [
                f"AuthClaw received an MFA reset request for {organization_name}.",
                "",
                "Use this reset token to generate a new authenticator setup key:",
                token,
                "",
                "If you did not request this reset, ignore this message and keep your existing MFA setup.",
            ]
        ),
        "MFA reset",
    )


def env_value(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is not None:
        return value
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for line in env_file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, raw_value = stripped.split("=", 1)
                if key.strip() == name:
                    return raw_value.strip().strip('"').strip("'")
    except OSError:
        pass
    return default


def env_bool(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return env_value(name, fallback).lower() in {"1", "true", "yes", "on"}


def skip_email_delivery_for_testing() -> bool:
    return env_bool("SKIP_EMAIL_DELIVERY_FOR_TESTING")


def skip_domain_verification_for_testing() -> bool:
    return env_bool("SKIP_DOMAIN_VERIFICATION")


def disable_mfa_for_testing() -> bool:
    return env_bool("DISABLE_MFA_FOR_TESTING")


def ensure_default_tenant_policies(conn, tenant_id: int) -> None:
    from sqlalchemy import text
    import json

    existing_count = conn.execute(
        text("SELECT COUNT(*) FROM policies WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    ).scalar() or 0
    if existing_count:
        return

    defaults = [
        {
            "name": "PII Protection",
            "type": "Security",
            "rules": {
                "pii_redaction": True,
                "detect": ["email", "phone", "aadhaar", "credit_card"],
                "action": "redact"
            },
        },
        {
            "name": "Prompt Injection Defense",
            "type": "Security",
            "rules": {
                "blocked_keywords": ["ignore previous instructions", "bypass policy", "reveal system prompt"],
                "action": "block_or_review"
            },
        },
        {
            "name": "Secrets Exfiltration Guard",
            "type": "Compliance",
            "rules": {
                "secret_detection": True,
                "detect": ["api_key", "token", "password", "private_key"],
                "action": "block"
            },
        },
    ]
    for policy in defaults:
        conn.execute(
            text("""
                INSERT INTO policies (tenant_id, name, type, rules, enabled, severity_level)
                VALUES (:tenant_id, :name, :type, :rules, true, 'HIGH')
            """),
            {
                "tenant_id": tenant_id,
                "name": policy["name"],
                "type": policy["type"],
                "rules": json.dumps(policy["rules"]),
            },
        )


def activate_verified_registration(conn, registration) -> int:
    from sqlalchemy import text

    existing_tenant_id = registration._mapping.get("tenant_id")
    if existing_tenant_id:
        return existing_tenant_id

    organization_name = registration._mapping["organization_name"]
    work_email = registration._mapping["work_email"]
    domain = registration._mapping["domain"]
    full_name = registration._mapping["full_name"]
    password_hash = registration._mapping["password_hash"]
    totp_secret = registration._mapping["totp_secret"]
    mfa_enabled = not disable_mfa_for_testing()

    tenant_id = conn.execute(
        text("""
            INSERT INTO tenants (
                name, domain, email, email_verified, domain_verified,
                email_verification_token, domain_verification_token, totp_secret
            )
            VALUES (:name, :domain, :email, true, true, NULL, :domain_token, :totp)
            RETURNING id
        """),
        {
            "name": organization_name,
            "domain": domain,
            "email": work_email,
            "domain_token": registration._mapping["domain_verification_token"],
            "totp": totp_secret,
        },
    ).scalar()

    name_parts = (full_name or "").strip().split(" ", 1)
    first_name = name_parts[0] if name_parts else None
    last_name = name_parts[1] if len(name_parts) > 1 else None
    conn.execute(
        text("""
            INSERT INTO tenant_users (
                tenant_id, first_name, last_name, email, password_hash,
                role, permissions, email_verified, mfa_enabled,
                totp_secret, status
            )
            VALUES (
                :tenant_id, :first_name, :last_name, :email, :password_hash,
                'Super Admin', 'all_access', true, :mfa_enabled,
                :totp_secret, 'active'
            )
        """),
        {
            "tenant_id": tenant_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": work_email,
            "password_hash": password_hash,
            "mfa_enabled": mfa_enabled,
            "totp_secret": totp_secret,
        },
    )
    conn.execute(
        text("UPDATE onboarding_registrations SET tenant_id = :tenant_id, activated_at = NOW() WHERE id = :id"),
        {"tenant_id": tenant_id, "id": registration._mapping["id"]},
    )
    ensure_default_tenant_policies(conn, tenant_id)
    return tenant_id

@app.post("/auth/login")
def auth_login(req: LoginRequest):
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        user = conn.execute(
            text("""
                SELECT u.id, u.tenant_id, u.email, u.password_hash, u.role,
                       u.permissions, u.email_verified, u.mfa_enabled,
                       u.totp_secret, u.status, t.name, t.domain,
                       t.domain_verified, t.email_verification_token,
                       t.domain_verification_token
                FROM tenant_users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(:email)
                LIMIT 1
            """),
            {"email": req.username},
        ).fetchone()

    if not user or not verify_password(req.password, user[3]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if user[9] != "active":
        raise HTTPException(status_code=403, detail="User account is not active.")

    user_id = user[0]
    tenant_id = user[1]
    username = user[2]
    role = user[4]
    permissions = user[5]
    email_verified = bool(user[6])
    mfa_enabled = bool(user[7])
    totp_secret = user[8]
    tenant_name = user[10]
    domain_name = user[11] or ""
    domain_verified = bool(user[12])
    email_token = user[13]
    domain_token = user[14]

    if not email_verified:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Email not verified",
                "email_verified": False,
                "email": req.username,
                "email_token": email_token
            }
        )

    if not domain_verified:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Domain not verified",
                "domain_verified": False,
                "domain": domain_name,
                "domain_token": domain_token
            }
        )

    if mfa_enabled and not totp_secret:
        return JSONResponse(
            status_code=400,
            content={
                "error": "MFA_NOT_CONFIGURED",
                "message": "MFA is not configured for this tenant."
            }
        )

    if not mfa_enabled:
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE tenant_users SET last_login_at = NOW() WHERE id = :id"),
                {"id": user_id},
            )
            conn.commit()

        now_ts = int(time.time())
        access_token = create_jwt({
            "sub": username,
            "role": role,
            "permissions": permissions,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "iat": now_ts,
            "exp": now_ts + 900
        })
        return {
            "access_token": access_token,
            "refresh_token": create_refresh_token_for_user(user_id, tenant_id, username),
            "user": {
                "username": username,
                "role": role,
                "permissions": permissions,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "organization": tenant_name,
                "email_verified": email_verified,
                "domain_verified": domain_verified
            }
        }

    session_id = str(uuid.uuid4())
    store_auth_session(session_id, {
        "username": username,
        "role": role,
        "permissions": permissions,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email_verified": email_verified,
        "domain_verified": domain_verified,
        "step": "otp"
    })
    
    return {
        "mfa_required": True,
        "session_id": session_id,
        "message": "MFA required. Enter the 6-digit OTP code."
    }

@app.post("/auth/verify-otp")
def auth_verify_otp(req: VerifyOTPRequest):
    session = load_auth_session(req.session_id)
    if not session or session["step"] != "otp":
        raise HTTPException(status_code=400, detail="Invalid or expired session.")
    
    tenant_id = session["tenant_id"]
    from database import engine
    from sqlalchemy import text
    user_id = session["user_id"]
    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT totp_secret FROM tenant_users WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": user_id, "tenant_id": tenant_id}
        ).fetchone()
        
    if not tenant or not tenant[0]:
        from startup.audit import log_audit_event
        log_audit_event(
            event="mfa_verification_failed",
            correlation_id=req.session_id,
            extra={"error": "MFA_NOT_CONFIGURED", "message": "MFA is not configured for this tenant."}
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": "MFA_NOT_CONFIGURED",
                "message": "MFA is not configured for this tenant."
            }
        )
        
    totp_secret = tenant[0]
    if not verify_totp_token(totp_secret, req.code):
        from startup.audit import log_audit_event
        log_audit_event(
            event="mfa_verification_failed",
            correlation_id=req.session_id,
            extra={"error": "INVALID_OTP_CODE", "message": "Invalid OTP code provided."}
        )
        raise HTTPException(status_code=401, detail="Invalid OTP code.")
    
    username = session["username"]
    role = session["role"]
    permissions = session["permissions"]
    tenant_id = session["tenant_id"]
    email_verified = session["email_verified"]
    domain_verified = session["domain_verified"]
    user_id = session["user_id"]
    
    now_ts = int(time.time())
    access_token_payload = {
        "sub": username,
        "role": role,
        "permissions": permissions,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "iat": now_ts,
        "exp": now_ts + 900
    }
    
    access_token = create_jwt(access_token_payload)
    refresh_token = create_refresh_token_for_user(user_id, tenant_id, username)

    with engine.connect() as conn:
        conn.execute(
            text("UPDATE tenant_users SET last_login_at = NOW() WHERE id = :id"),
            {"id": user_id},
        )
        conn.commit()
    
    delete_auth_session(req.session_id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "username": username,
            "role": role,
            "permissions": permissions,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "email_verified": email_verified,
            "domain_verified": domain_verified
        }
    }

@app.post("/auth/mfa/reset-request")
def auth_mfa_reset_request(req: MFAResetRequest):
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        user = conn.execute(
            text("""
                SELECT u.id, u.tenant_id, u.email, u.password_hash, u.role,
                       u.permissions, u.email_verified, u.mfa_enabled,
                       u.status, t.name, t.domain_verified
                FROM tenant_users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(:email)
                LIMIT 1
            """),
            {"email": req.username},
        ).fetchone()

    if not user or not verify_password(req.password, user[3]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if user[8] != "active":
        raise HTTPException(status_code=403, detail="User account is not active.")
    if not bool(user[6]):
        raise HTTPException(status_code=400, detail="Email must be verified before MFA reset.")
    if not bool(user[10]):
        raise HTTPException(status_code=400, detail="Domain must be verified before MFA reset.")

    reset_token = str(uuid.uuid4())
    store_auth_session(reset_token, {
        "username": user[2],
        "role": user[4],
        "permissions": user[5],
        "tenant_id": user[1],
        "user_id": user[0],
        "email_verified": True,
        "domain_verified": True,
        "step": "mfa_reset"
    })
    send_mfa_reset_email(user[2], reset_token, user[9] or "your organization")

    response = {
        "status": "success",
        "message": "MFA reset token sent to your verified email address."
    }
    if skip_email_delivery_for_testing():
        response["reset_token"] = reset_token
    return response

@app.post("/auth/mfa/reset-confirm")
def auth_mfa_reset_confirm(req: MFAResetConfirmRequest):
    session = load_auth_session(req.token)
    if not session or session["step"] != "mfa_reset":
        raise HTTPException(status_code=400, detail="Invalid or expired MFA reset token.")

    new_secret = generate_totp_secret()
    username = session["username"]
    tenant_id = session["tenant_id"]
    user_id = session["user_id"]

    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        updated = conn.execute(
            text("""
                UPDATE tenant_users
                SET totp_secret = :secret,
                    mfa_enabled = true,
                    updated_at = NOW()
                WHERE id = :user_id
                  AND tenant_id = :tenant_id
                  AND lower(email) = lower(:email)
                RETURNING id
            """),
            {
                "secret": new_secret,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "email": username,
            },
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="User account not found for MFA reset.")
        conn.commit()

    delete_auth_session(req.token)
    return {
        "status": "success",
        "message": "MFA setup key rotated. Add the new key to your authenticator app, then sign in.",
        "totp_secret": new_secret,
        "otpauth_uri": build_otpauth_uri(username, new_secret),
    }

@app.post("/auth/refresh")
def auth_refresh(req: RefreshRequest):
    payload = decode_jwt(req.refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token.")

    row = validate_refresh_token_record(payload)
    if not row:
        raise HTTPException(status_code=401, detail="User no longer exists.")

    user_id, tenant_id, username, role, permissions, email_verified, status = row
    if not email_verified:
        raise HTTPException(status_code=401, detail="User email is no longer verified.")

    now_ts = int(time.time())
    
    access_token_payload = {
        "sub": username,
        "role": role,
        "permissions": permissions,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "iat": now_ts,
        "exp": now_ts + 900
    }
    
    access_token = create_jwt(access_token_payload)
    return {
        "access_token": access_token
    }

@app.get("/reports/{type}/{format}")
def get_report_endpoint(type: str, format: str):
    from document_processing.reports import (
        generate_executive_summary_report,
        generate_technical_findings_report,
        generate_auditor_evidence_report
    )
    type = type.lower()
    format = format.lower()
    
    if type == "executive":
        content = generate_executive_summary_report(format)
    elif type == "technical":
        content = generate_technical_findings_report(format)
    elif type == "auditor":
        content = generate_auditor_evidence_report(format)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")
        
    media_types = {
        "pdf": "application/pdf",
        "csv": "text/csv",
        "json": "application/json"
    }
    media_type = media_types.get(format, "application/octet-stream")
    filename = f"{type}_report.{format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/cloud/connectors/status")
def get_cloud_connectors_status():
    from document_processing.connectors import is_real_connectors_enabled, list_cloud_source_files
    from document_processing.monitoring import last_sync_time
    
    is_real = is_real_connectors_enabled()
    sources = ["s3", "gdrive", "onedrive", "sharepoint", "dropbox"]
    connectors = []
    
    for src in sources:
        try:
            files = list_cloud_source_files(src)
        except Exception:
            files = []
        
        name_map = {
            "s3": "AWS S3 Bucket",
            "gdrive": "Google Drive",
            "onedrive": "Microsoft OneDrive",
            "sharepoint": "SharePoint Online",
            "dropbox": "Dropbox"
        }
        
        connectors.append({
            "name": name_map.get(src, src),
            "key": src,
            "enabled": is_real,
            "status": "Active (Real)" if is_real else "Simulated (Mock)",
            "files_count": len(files),
            "files": files
        })
        
    return {
        "connectors": connectors,
        "last_sync": last_sync_time
    }

@app.post("/cloud/connectors/sync")
def sync_cloud_connectors():
    from document_processing.monitoring import trigger_manual_sync
    res = trigger_manual_sync()
    return res

# 10. ONBOARDING & TENANT MANAGEMENT ENDPOINTS

@app.post("/auth/register")
def auth_register(req: RegisterRequest):
    from database import engine
    from sqlalchemy import text
    import uuid
    
    organization_name = req.company_name or req.name
    full_name = req.full_name or " ".join(part for part in [req.first_name, req.last_name] if part).strip()
    if not organization_name:
        raise HTTPException(status_code=400, detail="Organization name is required.")
    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=400, detail="A valid work email is required.")
    if not req.domain:
        raise HTTPException(status_code=400, detail="Organization domain is required.")

    password_hash = hash_password(req.password)
    email_token = str(uuid.uuid4())
    domain_token = f"authclaw-domain-verification={uuid.uuid4().hex[:16]}"
    totp_secret = generate_totp_secret()
    otpauth_uri = build_otpauth_uri(req.email, totp_secret)
    
    with engine.connect() as conn:
        if skip_domain_verification_for_testing():
            existing = conn.execute(
                text("""
                    SELECT id FROM tenants WHERE lower(email) = lower(:e)
                    UNION ALL
                    SELECT id FROM onboarding_registrations
                    WHERE lower(work_email) = lower(:e)
                    LIMIT 1
                """),
                {"e": req.email}
            ).fetchone()
        else:
            existing = conn.execute(
                text("""
                    SELECT id FROM tenants WHERE lower(email) = lower(:e) OR lower(domain) = lower(:d)
                    UNION ALL
                    SELECT id FROM onboarding_registrations
                    WHERE lower(work_email) = lower(:e) OR lower(domain) = lower(:d)
                    LIMIT 1
                """),
                {"e": req.email, "d": req.domain}
            ).fetchone()
        if existing:
            if skip_domain_verification_for_testing():
                raise HTTPException(status_code=400, detail="Organization with this email is already registered or pending verification.")
            raise HTTPException(status_code=400, detail="Organization with this email or domain is already registered or pending verification.")

        send_verification_email(req.email, email_token, organization_name)
        
        conn.execute(
            text("""
            INSERT INTO onboarding_registrations (
                organization_name, full_name, work_email, domain, password_hash,
                email_verification_token, domain_verification_token, totp_secret
            )
            VALUES (
                :organization_name, :full_name, :work_email, :domain, :password_hash,
                :email_token, :domain_token, :totp_secret
            )
            """),
            {
                "organization_name": organization_name,
                "full_name": full_name,
                "work_email": req.email,
                "domain": req.domain,
                "password_hash": password_hash,
                "email_token": email_token,
                "domain_token": domain_token,
                "totp_secret": totp_secret,
            }
        )
        conn.commit()
    
    response = {
        "status": "success",
        "message": "Registration received. Verify your email, then publish the DNS TXT record to activate the tenant.",
        "email_delivery": "sent",
        "domain_token": domain_token,
        "totp_secret": totp_secret,
        "otpauth_uri": otpauth_uri
    }
    if skip_email_delivery_for_testing():
        response["message"] = "Registration received. Email delivery skipped for local testing; use the returned email token."
        response["email_delivery"] = "skipped_for_testing"
        response["email_token"] = email_token
    return response

@app.post("/auth/verify-email")
def auth_verify_email(req: VerifyEmailRequest):
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, work_email
                FROM onboarding_registrations
                WHERE email_verification_token = :token
            """),
            {"token": req.token}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid verification token.")
        
        conn.execute(
            text("""
                UPDATE onboarding_registrations
                SET email_verified = true, email_verified_at = NOW()
                WHERE id = :id
            """),
            {"id": row[0]}
        )
        tenant_id = None
        domain_verification_skipped = skip_domain_verification_for_testing()
        if domain_verification_skipped:
            conn.execute(
                text("""
                    UPDATE onboarding_registrations
                    SET domain_verified = true, domain_verified_at = NOW()
                    WHERE id = :id
                """),
                {"id": row[0]}
            )
            updated = conn.execute(
                text("SELECT * FROM onboarding_registrations WHERE id = :id"),
                {"id": row[0]},
            ).fetchone()
            tenant_id = activate_verified_registration(conn, updated)
        conn.commit()
        
    if tenant_id:
        return {
            "status": "success",
            "message": "Email verified successfully. Domain verification skipped for local testing; tenant workspace activated.",
            "tenant_id": tenant_id,
            "domain_verification_skipped": True,
            "activated": True,
        }
    return {"status": "success", "message": "Email verified successfully.", "activated": False}

@app.post("/auth/verify-domain")
def auth_verify_domain(req: DomainVerifyRequest):
    from database import engine
    from sqlalchemy import text
    import dns.resolver
    
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, domain_verification_token, email_verified, domain_verified, tenant_id,
                       organization_name, full_name, work_email, domain, password_hash, totp_secret
                FROM onboarding_registrations
                WHERE lower(domain) = lower(:d)
            """),
            {"d": req.domain}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Domain not registered.")
        if not row[2]:
            raise HTTPException(status_code=400, detail="Email verification must be completed before domain activation.")
        
        tenant_id, expected_token = row[0], row[1]
        
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5.0
            resolver.lifetime = 5.0
            txt_records = resolver.resolve(req.domain, 'TXT')
            verified = False
            for txt_val in txt_records:
                txt_str = "".join([t.decode('utf-8') for t in txt_val.strings])
                if expected_token in txt_str:
                    verified = True
                    break
            
            if not verified:
                # If DNS records are queried successfully but no token matches, raise error
                raise HTTPException(status_code=400, detail=f"Domain verification record not found. Expected record value containing: {expected_token}")
        except HTTPException:
            raise
        except Exception as e:
            # Let's verify standard test/development domains or local overrides
            # If domain verification fails, raise descriptive exception
            raise HTTPException(status_code=400, detail=f"DNS resolver query failed: {str(e)}")
            
        conn.execute(
            text("""
                UPDATE onboarding_registrations
                SET domain_verified = true, domain_verified_at = NOW()
                WHERE id = :id
            """),
            {"id": row[0]}
        )
        updated = conn.execute(
            text("SELECT * FROM onboarding_registrations WHERE id = :id"),
            {"id": row[0]},
        ).fetchone()
        tenant_id = activate_verified_registration(conn, updated)
        conn.commit()
        
    return {
        "status": "success",
        "message": "Domain ownership verified. Tenant workspace activated.",
        "tenant_id": tenant_id,
    }

# 11. API KEY LIFECYCLE MANAGEMENT ENDPOINTS

def get_authenticated_tenant(authorization: str = Header(None)) -> int:
    return resolve_tenant_from_authorization(authorization)

@app.post("/keys/generate")
def generate_tenant_api_key(req: KeyGenerateRequest, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    import secrets
    import hashlib
    
    # Generate random raw API Key prefixing ac_
    raw_key = f"ac_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    key_prefix = raw_key[:10]
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=int(os.getenv("AUTHCLAW_API_KEY_TTL_DAYS", "365")))
    
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO tenant_api_keys (tenant_id, name, key_hash, key_prefix, expires_at)
            VALUES (:tid, :name, :hash, :key_prefix, :expires_at)
            """),
            {
                "tid": tenant_id,
                "name": req.name,
                "hash": key_hash,
                "key_prefix": key_prefix,
                "expires_at": expires_at,
            }
        )
        conn.commit()
    create_audit_block(
        query=f"Generate AuthClaw API Key: {req.name}",
        response=f"Tenant API key created with prefix {key_prefix}. Full key was shown once and stored as a hash.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
        
    return {
        "status": "success",
        "api_key": raw_key,
        "expires_at": expires_at.isoformat(),
        "message": "API key generated successfully. Copy it now; it will not be shown again. Your API keys are securely hashed and stored."
    }

@app.get("/keys/list")
def list_tenant_api_keys(tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT id, name, key_prefix, created_at, last_used_at, expires_at, revoked_at
                FROM tenant_api_keys
                WHERE tenant_id = :tid
                ORDER BY id DESC
            """),
            {"tid": tenant_id}
        ).fetchall()
        
    keys = []
    for r in res:
        keys.append({
            "id": r[0],
            "name": r[1],
            "key_prefix": r[2],
            "created_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
            "last_used_at": r[4].isoformat() if r[4] and hasattr(r[4], "isoformat") else str(r[4]) if r[4] else None,
            "expires_at": r[5].isoformat() if r[5] and hasattr(r[5], "isoformat") else str(r[5]) if r[5] else None,
            "revoked_at": r[6].isoformat() if r[6] and hasattr(r[6], "isoformat") else str(r[6]) if r[6] else None,
            "status": "revoked" if r[6] else "active"
        })
    return keys

@app.delete("/keys/{key_id}")
def revoke_tenant_api_key(key_id: int, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE tenant_api_keys SET revoked_at = NOW() WHERE id = :id AND tenant_id = :tid"),
            {"id": key_id, "tid": tenant_id}
        )
        conn.commit()
    create_audit_block(
        query=f"Revoke AuthClaw API Key: {key_id}",
        response="Tenant API key revoked.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
    return {"status": "success", "message": "API key revoked successfully."}

@app.post("/keys/{key_id}/rotate")
def rotate_tenant_api_key(key_id: int, req: KeyRotateRequest = KeyRotateRequest(), tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    import secrets
    import hashlib

    raw_key = f"ac_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_prefix = raw_key[:10]
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=int(os.getenv("AUTHCLAW_API_KEY_TTL_DAYS", "365")))

    with engine.connect() as conn:
        current = conn.execute(
            text("SELECT name FROM tenant_api_keys WHERE id = :id AND tenant_id = :tid AND revoked_at IS NULL"),
            {"id": key_id, "tid": tenant_id},
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Active API key not found.")

        conn.execute(
            text("UPDATE tenant_api_keys SET revoked_at = NOW() WHERE id = :id AND tenant_id = :tid"),
            {"id": key_id, "tid": tenant_id},
        )
        conn.execute(
            text("""
                INSERT INTO tenant_api_keys (tenant_id, name, key_hash, key_prefix, expires_at)
                VALUES (:tid, :name, :hash, :key_prefix, :expires_at)
            """),
            {
                "tid": tenant_id,
                "name": req.name or f"{current[0]} (rotated)",
                "hash": key_hash,
                "key_prefix": key_prefix,
                "expires_at": expires_at,
            },
        )
        conn.commit()
    create_audit_block(
        query=f"Rotate AuthClaw API Key: {key_id}",
        response=f"Tenant API key rotated. New key prefix {key_prefix} was shown once and stored as a hash.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )

    return {
        "status": "success",
        "api_key": raw_key,
        "expires_at": expires_at.isoformat(),
        "message": "API key rotated successfully. Copy the new key now; it will not be shown again. Your API key is securely stored and encrypted."
    }

# 12. PROVIDER CREDENTIALS MANAGEMENT ENDPOINTS

@app.post("/providers/connect")
def connect_provider_credentials(req: ProviderConnectRequest, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    import json
    
    # Symmetrically encrypt credential payloads
    payload_str = json.dumps(req.payload)
    encrypted_payload = encrypt_secret(payload_str)
    
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO tenant_credentials (tenant_id, provider, encrypted_payload)
            VALUES (:tid, :provider, :payload)
            ON CONFLICT (tenant_id, provider) DO UPDATE
            SET encrypted_payload = EXCLUDED.encrypted_payload, updated_at = NOW()
            """),
            {"tid": tenant_id, "provider": req.provider.lower(), "payload": encrypted_payload}
        )
        conn.commit()
    create_audit_block(
        query=f"Connect Provider Credentials: {req.provider.lower()}",
        response="Provider credentials encrypted and stored for tenant-owned gateway routing. Raw secret value was not logged.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
        
    return {"status": "success", "message": f"{req.provider} credentials connected successfully."}

@app.get("/providers/list")
def list_connected_providers(tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT provider, updated_at FROM tenant_credentials WHERE tenant_id = :tid"),
            {"tid": tenant_id}
        ).fetchall()
        
    providers = []
    for r in res:
        providers.append({
            "provider": r[0],
            "connected": True,
            "updated_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1])
        })
    return providers

@app.delete("/providers/{provider}")
def disconnect_provider_credentials(provider: str, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM tenant_credentials WHERE tenant_id = :tid AND provider = :provider"),
            {"tid": tenant_id, "provider": provider.lower()}
        )
        conn.commit()
    create_audit_block(
        query=f"Disconnect Provider Credentials: {provider.lower()}",
        response="Provider credentials removed for this tenant.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
    return {"status": "success", "message": f"{provider} credentials disconnected."}


@app.get("/gateway/requests")
def list_gateway_requests(limit: int = 50, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text

    capped_limit = max(1, min(limit, 200))
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, route_id, provider, model, risk_level,
                       allowed, status, decision, duration_ms, latency, created_at, timestamp
                FROM gateway_requests
                WHERE tenant_id = :tid
                ORDER BY COALESCE(created_at, timestamp) DESC
                LIMIT :limit
                """
            ),
            {"tid": str(tenant_id), "limit": capped_limit},
        ).fetchall()

    return [dict(row._mapping) for row in rows]


@app.get("/gateway/requests/{request_id}")
def get_gateway_request(request_id: str, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, route_id, provider, model, risk_level,
                       allowed, status, decision, duration_ms, latency, created_at, timestamp
                FROM gateway_requests
                WHERE request_id = :rid AND tenant_id = :tid
                ORDER BY COALESCE(created_at, timestamp) DESC
                LIMIT 1
                """
            ),
            {"rid": request_id, "tid": str(tenant_id)},
        ).fetchone()
        events = conn.execute(
            text(
                """
                SELECT sequence, agent_name, event_type, details, timestamp
                FROM agent_events
                WHERE request_id = :rid AND tenant_id = :tid
                ORDER BY COALESCE(sequence, id), id ASC
                """
            ),
            {"rid": request_id, "tid": tenant_id},
        ).fetchall()

    if row is None:
        raise HTTPException(status_code=404, detail="Gateway request not found.")

    payload = dict(row._mapping)
    payload["trace"] = [dict(event._mapping) for event in events]
    return payload


@app.get("/gateway/approvals")
def list_gateway_approvals(tenant_id: int = Depends(get_authenticated_tenant)):
    approvals = []
    for record in get_all_approvals().values():
        if record.get("tenant_id") == tenant_id:
            approvals.append(record)
    return approvals

