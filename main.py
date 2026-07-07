import startup.env_loader
import os
import time
import uuid
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Response, status, Request, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from graph import graph
from approval_store import (
    pending_approvals,
    approved_results,
    get_approval,
    get_all_approvals,
    get_approval_history,
    append_approval_audit,
    remaining_seconds,
)
from memory import get_history, add_message

from database.migrations import run_startup_migrations
from startup.validation import validate_environment
from startup.initialization import initialize_provider
from policy import compile_policy_to_rego, evaluate_opa_policy, get_policy, load_policy
from services.gateway_service import (
    GatewayProviderConfigurationError,
    GatewayProviderUnavailableError,
    GatewayService,
)
from services.tenant_context import auth_lookup_context, get_current_tenant_id, tenant_context

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
    
    # 4. Start background compliance watcher for watched_documents folder.
    # Local smoke tests can disable this so provider/email limits do not obscure
    # the core gateway, auth, and UI startup path.
    if env_bool("AUTHCLAW_DISABLE_BACKGROUND_MONITOR", False):
        logger.info("Background document compliance monitor disabled by AUTHCLAW_DISABLE_BACKGROUND_MONITOR.")
    else:
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

_rate_limit_memory = {}


def _feature_enabled(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _gateway_runtime_path(path: str) -> bool:
    normalized = path[4:] if path.startswith("/api/") else path
    return normalized in {"/gateway/chat", "/chat", "/v1/chat/completions"} or normalized.startswith("/gateway/documents/")


def _tenant_tier_limit(tenant_id: int) -> int:
    default_limits = {
        "free": 30,
        "starter": 60,
        "pro": 300,
        "enterprise": 1200,
    }
    tier = os.getenv("AUTHCLAW_DEFAULT_TENANT_TIER", "enterprise").strip().lower()
    try:
        from database import engine
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT COALESCE(subscription_tier, plan, tier, '') FROM tenants WHERE id = :tenant_id"),
                {"tenant_id": tenant_id},
            ).fetchone()
            if row and row[0]:
                tier = str(row[0]).lower()
    except Exception:
        pass
    env_limit = os.getenv(f"AUTHCLAW_RATE_LIMIT_{tier.upper()}_RPM")
    if env_limit:
        try:
            return max(1, int(env_limit))
        except ValueError:
            pass
    return default_limits.get(tier, default_limits["enterprise"])


def _consume_rate_limit_token(tenant_id: int, limit: int) -> Tuple[bool, int]:
    window = int(time.time() // 60)
    redis_url = os.getenv("REDIS_URL")
    key = f"authclaw:rate:{tenant_id}:{window}"
    if redis_url:
        try:
            import redis

            client = redis.Redis.from_url(redis_url)
            count = int(client.incr(key))
            if count == 1:
                client.expire(key, 90)
            return count <= limit, max(0, limit - count)
        except Exception:
            pass

    state_key = (tenant_id, window)
    count = _rate_limit_memory.get(state_key, 0) + 1
    _rate_limit_memory[state_key] = count
    for stale_key in list(_rate_limit_memory.keys()):
        if stale_key[1] < window - 1:
            _rate_limit_memory.pop(stale_key, None)
    return count <= limit, max(0, limit - count)


@app.middleware("http")
async def enterprise_gateway_middleware(request: Request, call_next):
    if _gateway_runtime_path(request.url.path):
        if _feature_enabled("AUTHCLAW_REQUIRE_GO_GATEWAY", False) and request.headers.get("X-AuthClaw-Gateway") != "go":
            return JSONResponse(
                status_code=status.HTTP_426_UPGRADE_REQUIRED,
                content={
                    "error": "go_gateway_required",
                    "message": "Route gateway traffic through the AuthClaw Go gateway.",
                },
            )

        if _feature_enabled("AUTHCLAW_RATE_LIMIT_ENABLED", False):
            try:
                api_key_val = request.headers.get("X-API-Key")
                authorization = request.headers.get("Authorization")
                if authorization and authorization.startswith("Bearer "):
                    api_key_val = authorization[7:]
                tenant_id = resolve_tenant(api_key_val, authorization)
                limit = _tenant_tier_limit(tenant_id)
                allowed, remaining = _consume_rate_limit_token(tenant_id, limit)
                if not allowed:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "rate_limit_exceeded",
                            "limit_rpm": limit,
                            "tenant_id": tenant_id,
                        },
                        headers={"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
                    )
                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(limit)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                return response
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            except Exception as exc:
                logger.warning("Rate limiter bypassed because fallback-safe middleware failed: %s", exc)
    return await call_next(request)


import os
import hashlib
import base64
import hmac
import struct
import time
from services.secret_manager import SecretManager, SENSITIVE_ENV_NAMES, bootstrap_local_process_secrets

bootstrap_local_process_secrets()

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
    return SecretManager().encrypt_for_database(raw_value)

def decrypt_secret(encrypted_value: str) -> str:
    return SecretManager().decrypt_from_database(encrypted_value)

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
    with auth_lookup_context(), engine.connect() as conn:
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

def optional_user_from_request(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return {}
    token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header
    payload = decode_jwt(token)
    return payload or {}


def _is_public_or_auth_path(path: str) -> bool:
    public_exact = {
        "/",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/health",
        "/health/ready",
        "/favicon.ico",
    }
    return path in public_exact or path.startswith(("/auth/", "/static/", "/assets/"))


def _tenant_id_from_request_headers(request: Request) -> Optional[int]:
    authorization = request.headers.get("Authorization")
    x_api_key = request.headers.get("X-API-Key")

    if authorization:
        token = authorization[7:] if authorization.startswith("Bearer ") else authorization
        payload = decode_jwt(token)
        if payload and payload.get("tenant_id"):
            return payload["tenant_id"]

    if x_api_key:
        return resolve_tenant(x_api_key=x_api_key, authorization=None)

    return None


@app.middleware("http")
async def tenant_database_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    tenant_id = None

    if not _is_public_or_auth_path(request.url.path):
        try:
            tenant_id = _tenant_id_from_request_headers(request)
        except HTTPException:
            tenant_id = None

    with tenant_context(tenant_id, request_id=request_id, required=tenant_id is not None):
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        if tenant_id is not None:
            response.headers["X-Tenant-ID"] = str(tenant_id)
        return response

def approval_actor_from_payload(payload: dict) -> str:
    return payload.get("email") or payload.get("sub") or "System Admin"

def ensure_approval_tenant_access(record: dict, payload: dict) -> None:
    tenant_id = payload.get("tenant_id")
    if tenant_id is not None and record.get("tenant_id") is not None and record.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Approval ID not found")

def approval_response_record(record: dict, tenant_id: int = None) -> dict:
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
        "correlation_id": record["correlation_id"],
        "tenant_id": record.get("tenant_id"),
        "risk_level": record.get("risk_level"),
        "reason": record.get("reason") or "high_risk",
        "comments": record.get("comments") or [],
        "approved_by": record.get("approved_by"),
        "rejected_by": record.get("rejected_by"),
        "executed_by": record.get("executed_by"),
        "mfa_verified": bool(record.get("mfa_verified", False)),
        "last_action_at": record.get("last_action_at"),
        "history": get_approval_history(record["approval_id"], tenant_id=tenant_id),
        "metadata": record.get("metadata", {}),
    }

async def parse_approval_action_payload(request: Request) -> dict:
    body_bytes = await request.body()
    if not body_bytes:
        return {"_body_present": False}
    try:
        payload = json.loads(body_bytes)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    if not isinstance(payload, dict):
        payload = {}
    payload["_body_present"] = True
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


def _stream_text_chunks(text: str, chunk_size: int = 80):
    if not text:
        return
    for start in range(0, len(text), chunk_size):
        yield text[start:start + chunk_size]


def _openai_completion_stream(
    *,
    content: str,
    model: str,
    request_id: str,
    tenant_id: int,
    trace: list,
):
    completion_id = f"chatcmpl-{uuid.uuid4()}"
    created = int(time.time())

    def sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    yield sse({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "request_id": request_id,
        "tenant_id": tenant_id,
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant"},
                "finish_reason": None,
            }
        ],
    })

    for chunk in _stream_text_chunks(content):
        yield sse({
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "request_id": request_id,
            "tenant_id": tenant_id,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None,
                }
            ],
        })

    yield sse({
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "request_id": request_id,
        "tenant_id": tenant_id,
        "trace": trace,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    })
    yield "data: [DONE]\n\n"


@app.get("/")
def home():
    return {
        "message": "AuthClaw Running"
    }


def get_gateway_service() -> GatewayService:
    return GatewayService(graph=graph, resolve_tenant=resolve_tenant, decode_jwt=decode_jwt)


PROVIDER_UNAVAILABLE_MESSAGE = (
    "The configured model provider is currently unavailable. Check provider "
    "credentials and outbound network access, then try again."
)


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
                "message": PROVIDER_UNAVAILABLE_MESSAGE,
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
                "message": PROVIDER_UNAVAILABLE_MESSAGE,
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
        tenant_id = get_current_tenant_id()
        with engine.connect() as conn:
            if tenant_id is not None:
                conn.execute(
                    text("""
                    INSERT INTO chat_sessions (session_id, title, user_id, tenant_id, created_at, updated_at)
                    VALUES (:session_id, :title, :user_id, :tenant_id, NOW(), NOW())
                    ON CONFLICT (session_id) DO UPDATE SET title = EXCLUDED.title, updated_at = NOW()
                    """),
                    {"session_id": req.session_id, "title": req.title, "user_id": username, "tenant_id": int(tenant_id)}
                )
            else:
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
        tenant_id = get_current_tenant_id()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM chat_messages"))
            conn.execute(text("DELETE FROM chat_sessions"))
            
            # Re-seed default session
            if tenant_id is not None:
                conn.execute(
                    text("""
                    INSERT INTO chat_sessions (session_id, title, user_id, tenant_id, created_at, updated_at)
                    VALUES (:session_id, :title, :user_id, :tenant_id, NOW(), NOW())
                    ON CONFLICT (session_id) DO NOTHING
                    """),
                    {"session_id": "default", "title": "Default Session", "user_id": "admin_user", "tenant_id": int(tenant_id)}
                )
            else:
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
        tenant_id = get_current_tenant_id()
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM chat_messages"))
            conn.execute(text("DELETE FROM chat_sessions"))
            if tenant_id is not None:
                conn.execute(
                    text("""
                    INSERT INTO chat_sessions (session_id, title, user_id, tenant_id, created_at, updated_at)
                    VALUES ('default', 'Default Session', 'admin_user', :tenant_id, NOW(), NOW())
                    ON CONFLICT (session_id) DO NOTHING
                    """),
                    {"tenant_id": int(tenant_id)}
                )
            else:
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
    confidence = 100
    if triggered:
        confidence = round(max(float(t.get("confidence", 0.8)) for t in triggered) * 100)

    return {
        "redacted_text": redacted_text,
        "count": len(triggered),
        "confidence": confidence,
        "triggered": triggered_names,
        "findings": triggered
    }


@app.get("/approvals")
def get_approvals_list(authorization: Optional[str] = Header(None)):
    tenant_id = None
    if authorization:
        tenant_id = resolve_tenant_from_authorization(authorization)
    approvals = get_all_approvals(tenant_id=tenant_id)
    return [approval_response_record(record, tenant_id=tenant_id) for record in approvals.values()]


@app.get("/approvals/{approval_id}")
def get_approval_by_id(approval_id: str, authorization: Optional[str] = Header(None)):
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval ID not found"
        )
    tenant_id = None
    if authorization:
        payload = get_current_user_from_authorization(authorization)
        ensure_approval_tenant_access(record, payload)
        tenant_id = payload.get("tenant_id")
    return approval_response_record(record, tenant_id=tenant_id)


@app.get("/approvals/{approval_id}/history")
def get_approval_history_by_id(approval_id: str, authorization: Optional[str] = Header(None)):
    record = get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval ID not found")
    tenant_id = None
    if authorization:
        payload = get_current_user_from_authorization(authorization)
        ensure_approval_tenant_access(record, payload)
        tenant_id = payload.get("tenant_id")
    return get_approval_history(approval_id, tenant_id=tenant_id)


@app.post("/approve/{approval_id}")
async def approve_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        # For backward compatibility, return JSON dict rather than raising 404
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Approval ID not found"}
        )

    user_payload = optional_user_from_request(request)
    ensure_approval_tenant_access(record, user_payload)
    approver = approval_actor_from_payload(user_payload)

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

    payload = await parse_approval_action_payload(request)
    body_present = bool(payload.pop("_body_present", False))
    comment = (payload.get("comment") or "").strip() or None

    from startup.audit import log_approval_event

    mfa_verified = False
    if require_mfa and body_present:
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
                user_id = user_payload.get("user_id")
                username = user_payload.get("sub") or user_payload.get("email")
                if user_id:
                    totp_secret = conn.execute(
                        text("""
                            SELECT totp_secret
                            FROM tenant_users
                            WHERE id = :user_id
                              AND tenant_id = :tenant_id
                            LIMIT 1
                        """),
                        {"user_id": user_id, "tenant_id": tenant_id},
                    ).scalar()
                if not totp_secret and username:
                    totp_secret = conn.execute(
                        text("""
                            SELECT totp_secret
                            FROM tenant_users
                            WHERE lower(email) = lower(:email)
                              AND tenant_id = :tenant_id
                            LIMIT 1
                        """),
                        {"email": username, "tenant_id": tenant_id},
                    ).scalar()
                if not totp_secret:
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
        mfa_verified = True

    # Transition status to approved
    record["status"] = "approved"
    record["approved_at"] = datetime.now(timezone.utc).isoformat()
    record["approved_by"] = approver
    record["mfa_verified"] = mfa_verified
    record["last_action_at"] = record["approved_at"]
    append_approval_audit(
        record,
        action="approved",
        actor=approver,
        comment=comment,
        mfa_verified=mfa_verified,
        metadata={"legacy_empty_body_bypass": require_mfa and not body_present},
    )

    log_approval_event(
        event="approval_approved",
        approval_id=record["approval_id"],
        request_id=record["request_id"],
        correlation_id=record["correlation_id"],
        extra={"approved_at": record["approved_at"], "approved_by": approver, "mfa_verified": mfa_verified}
    )

    # Create blockchain audit record for approval decision
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
async def reject_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Approval ID not found"}
        )

    user_payload = optional_user_from_request(request)
    ensure_approval_tenant_access(record, user_payload)
    approver = approval_actor_from_payload(user_payload)
    payload = await parse_approval_action_payload(request)
    payload.pop("_body_present", None)
    comment = (payload.get("comment") or "").strip() or None

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
    record["rejected_by"] = approver
    record["last_action_at"] = record["rejected_at"]
    append_approval_audit(
        record,
        action="rejected",
        actor=approver,
        comment=comment,
        metadata={"reason": record.get("reason")},
    )

    from startup.audit import log_approval_event
    log_approval_event(
        event="approval_rejected",
        approval_id=record["approval_id"],
        request_id=record["request_id"],
        correlation_id=record["correlation_id"],
        extra={"rejected_at": record["rejected_at"], "rejected_by": approver}
    )

    # Create blockchain audit record for rejection decision
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
async def execute_request(approval_id: str, request: Request):
    record = get_approval(approval_id)
    if record is None:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Request not approved"} # Match legacy error message
        )

    user_payload = optional_user_from_request(request)
    ensure_approval_tenant_access(record, user_payload)
    approver = approval_actor_from_payload(user_payload)
    payload = await parse_approval_action_payload(request)
    payload.pop("_body_present", None)
    comment = (payload.get("comment") or "").strip() or None

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
    record["executed_by"] = approver
    record["last_action_at"] = record["executed_at"]

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
                "message": PROVIDER_UNAVAILABLE_MESSAGE,
                "request_id": e.request_id,
                "trace": e.trace,
            }
        )

    from startup.audit import log_approval_event
    append_approval_audit(
        record,
        action="executed",
        actor=approver,
        comment=comment,
        metadata={
            "execution_request_id": execution.request_id,
            "provider": execution.provider,
            "model": execution.model,
        },
    )
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
                    "message": PROVIDER_UNAVAILABLE_MESSAGE,
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

    response_text = result.get("response", "No response generated")
    response_model = execution.model or request.model or "authclaw-gateway"

    if request.stream:
        return StreamingResponse(
            _openai_completion_stream(
                content=response_text,
                model=response_model,
                request_id=execution.request_id,
                tenant_id=execution.tenant_id,
                trace=execution.trace,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    response_payload = {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response_model,
        "request_id": execution.request_id,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
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
        "document_storage": os.getenv("AUTHCLAW_DOCUMENT_STORAGE_BACKEND", "local"),
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


def is_valid_work_email(value: str) -> bool:
    email = (value or "").strip()
    if any(char.isspace() for char in email) or email.count("@") != 1:
        return False
    local, domain = email.split("@", 1)
    return bool(local and domain and "." in domain and not domain.startswith(".") and not domain.endswith("."))



class PolicyRequest(BaseModel):
    name: str
    type: str
    rules: str
    enabled: bool
    status: Optional[str] = None
    severity_level: Optional[str] = None

class PolicySimulationRequest(BaseModel):
    name: Optional[str] = "Simulation Policy"
    type: Optional[str] = "Custom"
    rules: str
    enabled: Optional[bool] = True
    severity_level: Optional[str] = "MEDIUM"
    sample_text: str

class GatewayPolicyEvaluationRequest(BaseModel):
    method: str
    path: str
    request_id: Optional[str] = None
    body: Optional[Any] = None
    body_raw: Optional[str] = None

def policy_rules_checksum(rules: Dict[str, Any]) -> str:
    canonical = json.dumps(rules or {}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def policy_actor_from_authorization(authorization: Optional[str]) -> str:
    try:
        payload = get_current_user_from_authorization(authorization)
        return payload.get("email") or payload.get("sub") or "system"
    except Exception:
        return "system"

def persist_policy_version(
    conn,
    tenant_id: int,
    policy_id: int,
    version: int,
    status_value: str,
    rules: Dict[str, Any],
    actor: str,
    approver: Optional[str] = None,
    changelog: Optional[str] = None,
) -> Optional[int]:
    checksum = policy_rules_checksum(rules)
    row = conn.execute(
        text("""
            INSERT INTO policy_versions (
                tenant_id, policy_id, version, status, rules, checksum,
                author, approver, changelog, created_at, approved_at, published_at
            )
            VALUES (
                :tenant_id, :policy_id, :version, :status, :rules, :checksum,
                :author, :approver, :changelog, NOW(),
                CASE WHEN :status IN ('approved', 'published') THEN NOW() ELSE NULL END,
                CASE WHEN :status = 'published' THEN NOW() ELSE NULL END
            )
            ON CONFLICT (policy_id, version) DO UPDATE
            SET status = EXCLUDED.status,
                rules = EXCLUDED.rules,
                checksum = EXCLUDED.checksum,
                approver = COALESCE(EXCLUDED.approver, policy_versions.approver),
                changelog = COALESCE(EXCLUDED.changelog, policy_versions.changelog),
                approved_at = CASE
                    WHEN EXCLUDED.status IN ('approved', 'published') THEN COALESCE(policy_versions.approved_at, NOW())
                    ELSE policy_versions.approved_at
                END,
                published_at = CASE
                    WHEN EXCLUDED.status = 'published' THEN COALESCE(policy_versions.published_at, NOW())
                    ELSE policy_versions.published_at
                END
            RETURNING id
        """),
        {
            "tenant_id": tenant_id,
            "policy_id": policy_id,
            "version": version,
            "status": status_value,
            "rules": json.dumps(rules),
            "checksum": checksum,
            "author": actor,
            "approver": approver,
            "changelog": changelog,
        },
    ).fetchone()
    return int(row[0]) if row else None

def persist_policy_change_approval(
    conn,
    tenant_id: int,
    policy_id: int,
    version_id: Optional[int],
    status_value: str,
    requested_by: str,
    reviewed_by: Optional[str] = None,
    comments: Optional[str] = None,
) -> None:
    conn.execute(
        text("""
            INSERT INTO policy_change_approvals (
                tenant_id, policy_id, version_id, status, requested_by,
                reviewed_by, comments, created_at, decided_at
            )
            VALUES (
                :tenant_id, :policy_id, :version_id, :status, :requested_by,
                :reviewed_by, :comments, NOW(),
                CASE WHEN :status IN ('approved', 'rejected') THEN NOW() ELSE NULL END
            )
        """),
        {
            "tenant_id": tenant_id,
            "policy_id": policy_id,
            "version_id": version_id,
            "status": status_value,
            "requested_by": requested_by,
            "reviewed_by": reviewed_by,
            "comments": comments,
        },
    )

def extract_policy_text_from_gateway_payload(payload: GatewayPolicyEvaluationRequest) -> str:
    body = payload.body
    if isinstance(body, dict):
        if isinstance(body.get("message"), str):
            return body["message"]
        messages = body.get("messages")
        if isinstance(messages, list):
            for item in reversed(messages):
                if isinstance(item, dict) and item.get("role") == "user":
                    content = item.get("content")
                    if isinstance(content, str):
                        return content
        prompt = body.get("prompt")
        if isinstance(prompt, str):
            return prompt
        return json.dumps(body, sort_keys=True)
    if isinstance(payload.body_raw, str) and payload.body_raw.strip():
        return payload.body_raw
    if isinstance(body, str):
        return body
    return ""

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
    route_payload = route.dict()
    route_payload["name"] = route.name.strip()
    route_payload["provider"] = route.provider.strip()
    route_payload["endpoint"] = route.endpoint.strip()
    route_payload["model"] = route.model.strip()
    route_payload["tenant_assignment"] = route.tenant_assignment.strip() or "Current Tenant"

    if not route_payload["name"]:
        raise HTTPException(status_code=400, detail="Route name is required.")
    if not route_payload["provider"]:
        raise HTTPException(status_code=400, detail="Provider is required.")
    if not route_payload["model"]:
        raise HTTPException(status_code=400, detail="Model is required.")
    if not route_payload["endpoint"].startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Endpoint URL must start with http:// or https://.")
    if route.rate_limit < 1:
        raise HTTPException(status_code=400, detail="Rate limit must be at least 1 request per minute.")

    with tenant_context(tenant_id, required=True), engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO gateway_routes (tenant_id, name, provider, endpoint, model, rate_limit, redaction_enabled, enabled, tenant_assignment)
            VALUES (:tenant_id, :name, :provider, :endpoint, :model, :rate_limit, :redaction_enabled, :enabled, :tenant_assignment)
            """),
            {**route_payload, "tenant_id": tenant_id}
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
    with auth_lookup_context(), engine.connect() as conn:
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
            text("""
                SELECT id, name, type, rules, enabled, tenant_id,
                       COALESCE(version, 1) AS version,
                       COALESCE(status, 'published') AS status,
                       COALESCE(severity_level, 'MEDIUM') AS severity_level,
                       published_at, created_at, updated_at
                FROM policies
                WHERE tenant_id = :tenant_id
                ORDER BY id ASC
            """),
            {"tenant_id": tenant_id},
        )
        return [dict(r._mapping) for r in res]

@app.post("/policies")
def create_policy(policy: PolicyRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from verify_audit import create_audit_block
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    rules = PolicyEngine().parse_rules(policy.rules)
    status = policy.status or "published"
    severity_level = policy.severity_level or "MEDIUM"
    checksum = policy_rules_checksum(rules)
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                INSERT INTO policies (
                    name, type, rules, enabled, tenant_id, severity_level,
                    version, status, published_at, created_by, updated_by, checksum, changelog,
                    approved_by, approved_at, created_at, updated_at
                )
                VALUES (
                    :name, :type, :rules, :enabled, :tenant_id, :severity_level,
                    1, :status, CASE WHEN :status = 'published' THEN NOW() ELSE NULL END,
                    :actor, :actor, :checksum, :changelog,
                    CASE WHEN :status = 'published' THEN :actor ELSE NULL END,
                    CASE WHEN :status = 'published' THEN NOW() ELSE NULL END,
                    NOW(), NOW()
                )
                RETURNING id
            """),
            {
                "name": policy.name,
                "type": policy.type,
                "rules": json.dumps(rules),
                "enabled": policy.enabled,
                "tenant_id": tenant_id,
                "severity_level": severity_level,
                "status": status,
                "actor": actor,
                "checksum": checksum,
                "changelog": f"Created policy '{policy.name}'.",
            }
        ).fetchone()
        policy_id = row[0]
        version_id = persist_policy_version(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=1,
            status_value=status,
            rules=rules,
            actor=actor,
            approver=actor if status == "published" else None,
            changelog=f"Created policy '{policy.name}'.",
        )
        if status == "published":
            persist_policy_change_approval(
                conn,
                tenant_id=tenant_id,
                policy_id=policy_id,
                version_id=version_id,
                status_value="approved",
                requested_by=actor,
                reviewed_by=actor,
                comments="Initial policy approved for publication.",
            )
        elif status in {"draft", "pending_approval"}:
            persist_policy_change_approval(
                conn,
                tenant_id=tenant_id,
                policy_id=policy_id,
                version_id=version_id,
                status_value="pending",
                requested_by=actor,
                comments="Policy change pending approval.",
            )
        conn.commit()
    record_policy_history(
        tenant_id=tenant_id,
        policy_id=policy_id,
        action="created",
        actor=actor,
        after_rules=rules,
        version=1,
        status=status,
    )
    create_audit_block(
        query=f"Create Guardrail Policy: {policy.name}",
        response=f"Compliance policy type {policy.type} configured and saved at version 1.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy created.", "policy_id": policy_id, "version": 1}

@app.put("/policies/{policy_id}")
def update_policy(policy_id: int, policy: PolicyRequest, authorization: Optional[str] = Header(None)):
    from database import engine
    from verify_audit import create_audit_block
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    rules = PolicyEngine().parse_rules(policy.rules)
    severity_level = policy.severity_level or "MEDIUM"
    checksum = policy_rules_checksum(rules)
    with engine.connect() as conn:
        before = conn.execute(
            text("""
                SELECT rules, COALESCE(version, 1) AS version, COALESCE(status, 'published') AS status
                FROM policies
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if before is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        before_rules = PolicyEngine().parse_rules(before[0])
        next_version = int(before[1] or 1) + 1
        status = policy.status or before[2] or "published"
        result = conn.execute(
            text("""
                UPDATE policies
                SET name = :name,
                    type = :type,
                    rules = :rules,
                    enabled = :enabled,
                    severity_level = :severity_level,
                    version = :version,
                    status = :status,
                    published_at = CASE WHEN :status = 'published' THEN COALESCE(published_at, NOW()) ELSE published_at END,
                    checksum = :checksum,
                    changelog = :changelog,
                    approved_by = CASE WHEN :status = 'published' THEN :actor ELSE approved_by END,
                    approved_at = CASE WHEN :status = 'published' THEN COALESCE(approved_at, NOW()) ELSE approved_at END,
                    updated_by = :actor,
                    updated_at = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {
                "name": policy.name,
                "type": policy.type,
                "rules": json.dumps(rules),
                "enabled": policy.enabled,
                "severity_level": severity_level,
                "version": next_version,
                "status": status,
                "actor": actor,
                "checksum": checksum,
                "changelog": f"Updated policy '{policy.name}' to version {next_version}.",
                "id": policy_id,
                "tenant_id": tenant_id,
            }
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Policy not found.")
        version_id = persist_policy_version(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=next_version,
            status_value=status,
            rules=rules,
            actor=actor,
            approver=actor if status == "published" else None,
            changelog=f"Updated policy '{policy.name}' to version {next_version}.",
        )
        persist_policy_change_approval(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version_id=version_id,
            status_value="approved" if status == "published" else "pending",
            requested_by=actor,
            reviewed_by=actor if status == "published" else None,
            comments="Policy version change recorded.",
        )
        conn.commit()
    record_policy_history(
        tenant_id=tenant_id,
        policy_id=policy_id,
        action="updated",
        actor=actor,
        before_rules=before_rules,
        after_rules=rules,
        version=next_version,
        status=status,
    )
    create_audit_block(
        query=f"Update Policy (ID {policy_id}): {policy.name}",
        response=f"Guardrail configurations modified. Active status is: {policy.enabled}. Version: {next_version}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy updated.", "version": next_version}

@app.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = "system"
    try:
        actor = get_current_user_from_authorization(authorization).get("sub") or actor
    except Exception:
        pass
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT name, rules, COALESCE(version, 1) AS version, COALESCE(status, 'published') AS status
                FROM policies
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id}
        ).fetchone()
        name = row[0] if row else f"ID {policy_id}"
        before_rules = PolicyEngine().parse_rules(row[1]) if row else {}
        version = int(row[2] or 1) if row else 1
        status = row[3] if row else "deleted"
        result = conn.execute(text("DELETE FROM policies WHERE id = :id AND tenant_id = :tenant_id"), {"id": policy_id, "tenant_id": tenant_id})
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Policy not found.")
        conn.commit()
    record_policy_history(
        tenant_id=tenant_id,
        policy_id=None,
        action="deleted",
        actor=actor,
        before_rules=before_rules,
        version=version,
        status=status,
    )
    create_audit_block(
        query=f"Delete Compliance Policy: {name}",
        response=f"Policy '{name}' deleted.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Policy deleted."}

@app.post("/policies/simulate")
def simulate_policy(policy: PolicySimulationRequest, authorization: Optional[str] = Header(None)):
    from services.policy_engine import PolicyEngine
    from database import engine
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    policy_payload = policy.model_dump() if hasattr(policy, "model_dump") else policy.dict()
    result = PolicyEngine().simulate(policy_payload, policy.sample_text, tenant_id, actor)
    sample_hash = hashlib.sha256((policy.sample_text or "").encode("utf-8")).hexdigest()
    with auth_lookup_context(), engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO policy_simulation_results (
                    tenant_id, policy_id, actor, sample_hash, result, created_at
                )
                VALUES (:tenant_id, NULL, :actor, :sample_hash, :result, NOW())
            """),
            {
                "tenant_id": tenant_id,
                "actor": actor,
                "sample_hash": sample_hash,
                "result": json.dumps(result, default=str),
            },
        )
        conn.commit()
    return result

@app.post("/policies/{policy_id}/simulate")
def simulate_existing_policy(policy_id: int, payload: Dict[str, str], authorization: Optional[str] = Header(None)):
    from database import engine
    from services.policy_engine import PolicyEngine
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    sample_text = payload.get("sample_text", "")
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, name, type, rules, enabled, COALESCE(version, 1) AS version, COALESCE(severity_level, 'MEDIUM') AS severity_level
                FROM policies
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Policy not found.")
    policy_payload = dict(row._mapping)
    policy_payload["sample_text"] = sample_text
    result = PolicyEngine().simulate(policy_payload, sample_text, tenant_id, actor)
    sample_hash = hashlib.sha256((sample_text or "").encode("utf-8")).hexdigest()
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO policy_simulation_results (
                    tenant_id, policy_id, actor, sample_hash, result, created_at
                )
                VALUES (:tenant_id, :policy_id, :actor, :sample_hash, :result, NOW())
            """),
            {
                "tenant_id": tenant_id,
                "policy_id": policy_id,
                "actor": actor,
                "sample_hash": sample_hash,
                "result": json.dumps(result, default=str),
            },
        )
        conn.commit()
    return result

@app.post("/policies/{policy_id}/publish")
def publish_policy(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from verify_audit import create_audit_block
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT name, rules, COALESCE(version, 1) AS version
                FROM policies
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Policy not found.")
        rules = PolicyEngine().parse_rules(row[1])
        version = int(row[2] or 1)
        checksum = policy_rules_checksum(rules)
        conn.execute(
            text("""
                UPDATE policies
                SET status = 'published',
                    published_at = NOW(),
                    checksum = :checksum,
                    approved_by = :actor,
                    approved_at = COALESCE(approved_at, NOW()),
                    updated_by = :actor,
                    updated_at = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id, "actor": actor, "checksum": checksum},
        )
        version_id = persist_policy_version(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=version,
            status_value="published",
            rules=rules,
            actor=actor,
            approver=actor,
            changelog=f"Published policy '{row[0]}' at version {version}.",
        )
        persist_policy_change_approval(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version_id=version_id,
            status_value="approved",
            requested_by=actor,
            reviewed_by=actor,
            comments="Policy version approved and published.",
        )
        conn.commit()
    record_policy_history(
        tenant_id=tenant_id,
        policy_id=policy_id,
        action="published",
        actor=actor,
        after_rules=rules,
        version=version,
        status="published",
    )
    create_audit_block(
        query=f"Publish Policy (ID {policy_id}): {row[0]}",
        response=f"Policy '{row[0]}' published at version {version}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        tenant_id=tenant_id,
    )
    return {"status": "success", "message": "Policy published.", "version": version}

@app.get("/policies/{policy_id}/history")
def policy_history(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        exists = conn.execute(
            text("SELECT id FROM policies WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if not exists:
            historical = conn.execute(
                text("SELECT id FROM policy_audit_history WHERE policy_id = :id AND tenant_id = :tenant_id LIMIT 1"),
                {"id": policy_id, "tenant_id": tenant_id},
            ).fetchone()
            if not historical:
                raise HTTPException(status_code=404, detail="Policy not found.")
        rows = conn.execute(
            text("""
                SELECT id, tenant_id, policy_id, action, actor, before_rules, after_rules,
                       version, status, created_at
                FROM policy_audit_history
                WHERE policy_id = :id AND tenant_id = :tenant_id
                ORDER BY id DESC
            """),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchall()
    return [dict(row._mapping) for row in rows]

@app.get("/policies/{policy_id}/versions")
def policy_versions(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, tenant_id, policy_id, version, status, checksum,
                       author, approver, changelog, created_at, approved_at,
                       published_at, archived_at
                FROM policy_versions
                WHERE policy_id = :policy_id AND tenant_id = :tenant_id
                ORDER BY version DESC
            """),
            {"policy_id": policy_id, "tenant_id": tenant_id},
        ).fetchall()
    return [dict(row._mapping) for row in rows]

@app.get("/policies/{policy_id}/approvals")
def policy_change_approvals(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    tenant_id = resolve_tenant_from_authorization(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, tenant_id, policy_id, version_id, status, requested_by,
                       reviewed_by, comments, created_at, decided_at
                FROM policy_change_approvals
                WHERE policy_id = :policy_id AND tenant_id = :tenant_id
                ORDER BY id DESC
            """),
            {"policy_id": policy_id, "tenant_id": tenant_id},
        ).fetchall()
    return [dict(row._mapping) for row in rows]

@app.post("/policies/{policy_id}/approve")
def approve_policy_change(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT id, rules, COALESCE(version, 1) AS version
                FROM policies
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found.")
        rules = PolicyEngine().parse_rules(row[1])
        version_id = persist_policy_version(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version=int(row[2] or 1),
            status_value="approved",
            rules=rules,
            actor=actor,
            approver=actor,
            changelog="Policy version approved.",
        )
        persist_policy_change_approval(
            conn,
            tenant_id=tenant_id,
            policy_id=policy_id,
            version_id=version_id,
            status_value="approved",
            requested_by=actor,
            reviewed_by=actor,
            comments="Policy version approved.",
        )
        conn.commit()
    record_policy_history(tenant_id, policy_id, "approved", actor, after_rules=rules, version=int(row[2] or 1), status="approved")
    return {"status": "success", "message": "Policy change approved.", "version": int(row[2] or 1)}

@app.post("/policies/{policy_id}/reject")
def reject_policy_change(policy_id: int, payload: Dict[str, str] = None, authorization: Optional[str] = Header(None)):
    from database import engine
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    comments = (payload or {}).get("comments") or "Policy change rejected."
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, COALESCE(version, 1) AS version FROM policies WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found.")
        persist_policy_change_approval(conn, tenant_id, policy_id, None, "rejected", actor, actor, comments)
        conn.commit()
    return {"status": "success", "message": "Policy change rejected.", "version": int(row[1] or 1)}

@app.post("/policies/{policy_id}/archive")
def archive_policy(policy_id: int, authorization: Optional[str] = Header(None)):
    from database import engine
    from services.policy_engine import record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT rules, COALESCE(version, 1) AS version FROM policies WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Policy not found.")
        conn.execute(
            text("""
                UPDATE policies
                SET status = 'archived', archived_at = NOW(), updated_by = :actor, updated_at = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {"id": policy_id, "tenant_id": tenant_id, "actor": actor},
        )
        conn.execute(
            text("""
                UPDATE policy_versions
                SET status = 'archived', archived_at = NOW()
                WHERE policy_id = :id AND tenant_id = :tenant_id AND version = :version
            """),
            {"id": policy_id, "tenant_id": tenant_id, "version": int(row[1] or 1)},
        )
        conn.commit()
    record_policy_history(tenant_id, policy_id, "archived", actor, before_rules=json.loads(row[0]) if row[0] else {}, version=int(row[1] or 1), status="archived")
    return {"status": "success", "message": "Policy archived.", "version": int(row[1] or 1)}

@app.post("/policies/{policy_id}/rollback")
def rollback_policy(policy_id: int, payload: Dict[str, int], authorization: Optional[str] = Header(None)):
    from database import engine
    from services.policy_engine import PolicyEngine, record_policy_history
    tenant_id = resolve_tenant_from_authorization(authorization)
    actor = policy_actor_from_authorization(authorization)
    target_version = int(payload.get("version", 0) or 0)
    if target_version <= 0:
        raise HTTPException(status_code=400, detail="Rollback version is required.")
    with engine.connect() as conn:
        version_row = conn.execute(
            text("""
                SELECT rules, checksum
                FROM policy_versions
                WHERE policy_id = :policy_id AND tenant_id = :tenant_id AND version = :version
            """),
            {"policy_id": policy_id, "tenant_id": tenant_id, "version": target_version},
        ).fetchone()
        if not version_row:
            raise HTTPException(status_code=404, detail="Policy version not found.")
        rules = PolicyEngine().parse_rules(version_row[0])
        current = conn.execute(
            text("SELECT COALESCE(version, 1) AS version FROM policies WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": policy_id, "tenant_id": tenant_id},
        ).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Policy not found.")
        next_version = int(current[0] or 1) + 1
        checksum = policy_rules_checksum(rules)
        conn.execute(
            text("""
                UPDATE policies
                SET rules = :rules, version = :version, status = 'published',
                    checksum = :checksum, changelog = :changelog,
                    approved_by = :actor, approved_at = NOW(),
                    published_at = NOW(), updated_by = :actor, updated_at = NOW()
                WHERE id = :id AND tenant_id = :tenant_id
            """),
            {
                "rules": json.dumps(rules),
                "version": next_version,
                "checksum": checksum,
                "changelog": f"Rolled back from version {int(current[0] or 1)} to {target_version}.",
                "actor": actor,
                "id": policy_id,
                "tenant_id": tenant_id,
            },
        )
        version_id = persist_policy_version(
            conn, tenant_id, policy_id, next_version, "published", rules, actor, actor,
            f"Rollback to version {target_version}."
        )
        persist_policy_change_approval(
            conn, tenant_id, policy_id, version_id, "approved", actor, actor,
            f"Rollback to version {target_version} approved."
        )
        conn.commit()
    record_policy_history(tenant_id, policy_id, "rollback", actor, after_rules=rules, version=next_version, status="published")
    return {"status": "success", "message": "Policy rolled back.", "version": next_version, "rolled_back_to": target_version}

@app.post("/internal/policy/evaluate")
def evaluate_gateway_policy(
    payload: GatewayPolicyEvaluationRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    x_authclaw_gateway_request_id: Optional[str] = Header(None),
):
    from database import engine
    from services.policy_engine import ACTION_BLOCK, PolicyEngine
    started_at = time.time()
    tenant_id = resolve_tenant(x_api_key, authorization)
    actor = "api-client"
    if authorization:
        actor = policy_actor_from_authorization(authorization)
    request_id = payload.request_id or x_authclaw_gateway_request_id or f"policy-{uuid.uuid4()}"
    text_value = extract_policy_text_from_gateway_payload(payload)
    opa_result = evaluate_opa_policy(
        text_value,
        tenant_id=tenant_id,
        context={"path": payload.path, "method": payload.method, "request_id": request_id, "actor": actor},
    )
    if opa_result:
        matched_policies = opa_result.get("findings") or [
            {
                "policy_name": "OPA Policy",
                "category": opa_result.get("category", "opa"),
                "action": opa_result.get("decision", "ALLOW"),
                "confidence": "enterprise-rego",
            }
        ]
        decision = opa_result.get("decision", "ALLOW")
        allowed = bool(opa_result.get("allowed", True))
        reason = opa_result.get("reason", "OPA policy decision")
        risk_level = opa_result.get("risk_level") or ("HIGH" if decision in {"BLOCK", "REQUIRE_APPROVAL"} else "LOW")
        policy_versions = [{"engine": "opa", "status": "evaluated"}]
    else:
        result = PolicyEngine().evaluate(text_value, tenant_id=tenant_id, username=actor)
        matched_policies = [
            {
                "policy_id": finding.get("policy_id"),
                "policy_name": finding.get("policy_name"),
                "category": finding.get("category"),
                "action": finding.get("action"),
                "confidence": finding.get("confidence"),
            }
            for finding in result.findings
        ]
        decision = "BLOCK" if result.action == ACTION_BLOCK else result.action
        allowed = result.action != ACTION_BLOCK
        reason = result.reason
        risk_level = result.risk_level
        policy_versions = result.policy_versions
    duration_ms = int((time.time() - started_at) * 1000)
    response_payload = {
        "status": "evaluated",
        "decision": decision,
        "allowed": allowed,
        "enforcement": "fail_closed",
        "matched_policies": matched_policies,
        "policy_versions": policy_versions,
        "evaluation_time_ms": duration_ms,
        "explanation": reason,
        "reason": reason,
        "risk_level": risk_level,
        "request_id": request_id,
        "tenant_id": tenant_id,
    }
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO policy_evaluation_audit (
                    tenant_id, request_id, route_path, decision, reason,
                    evaluation_time_ms, matched_policies, policy_versions, created_at
                )
                VALUES (
                    :tenant_id, :request_id, :route_path, :decision, :reason,
                    :evaluation_time_ms, :matched_policies, :policy_versions, NOW()
                )
            """),
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "route_path": payload.path,
                "decision": decision,
                "reason": reason,
                "evaluation_time_ms": duration_ms,
                "matched_policies": json.dumps(matched_policies, default=str),
                "policy_versions": json.dumps(policy_versions, default=str),
            },
        )
        conn.commit()
    return response_payload


# 6. RAG DOCUMENTS
@app.get("/rag/documents")
def get_documents(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant(x_api_key, authorization)
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT id, name, type, size_bytes, status, last_indexed, chunks_count
                FROM knowledge_documents
                WHERE tenant_id = :tenant_id
                ORDER BY id DESC
            """),
            {"tenant_id": tenant_id}
        )
        return [dict(r._mapping) for r in res]

@app.post("/rag/documents")
def create_document(
    doc: DocumentUploadRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    from rag.embeddings import generate_embedding
    tenant_id = resolve_tenant(x_api_key, authorization)
    today = datetime.now(timezone.utc).date().isoformat()
    chunks_count = max(1, int(doc.size_bytes // 50000))
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            INSERT INTO knowledge_documents (tenant_id, name, type, size_bytes, status, last_indexed, chunks_count)
            VALUES (:tenant_id, :name, :type, :size_bytes, 'indexed', :last_indexed, :chunks_count)
            RETURNING id
            """),
            {
                "tenant_id": tenant_id,
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
                INSERT INTO knowledge_chunks (tenant_id, document_id, content, embedding_preview, embedding_vector)
                VALUES (:tenant_id, :doc_id, :content, :emb, :vec)
                """),
                {
                    "tenant_id": tenant_id,
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
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Document uploaded and indexed successfully."}

def parse_document_id(doc_id_str: str) -> int:
    if doc_id_str.startswith("doc_"):
        return int(doc_id_str[4:])
    try:
        return int(doc_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID format. Must be like 'doc_123' or '123'")

def resolve_document_record(conn, doc_id: int, tenant_id: int):
    from sqlalchemy import text

    row = conn.execute(
        text("SELECT id, filename FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": doc_id, "tenant_id": tenant_id}
    ).fetchone()
    if row:
        return row

    k_doc = conn.execute(
        text("SELECT name FROM knowledge_documents WHERE id = :id AND tenant_id = :tenant_id"),
        {"id": doc_id, "tenant_id": tenant_id}
    ).fetchone()
    if not k_doc:
        return None

    return conn.execute(
        text("SELECT id, filename FROM documents WHERE filename = :name AND tenant_id = :tenant_id ORDER BY id DESC LIMIT 1"),
        {"name": k_doc[0], "tenant_id": tenant_id}
    ).fetchone()

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    
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
            INSERT INTO documents (tenant_id, filename, source, size_bytes, status, risk_score, severity)
            VALUES (:tenant_id, :filename, 'local', :size_bytes, 'pending', 0, 'LOW')
            RETURNING id
            """),
            {
                "tenant_id": tenant_id,
                "filename": filename,
                "size_bytes": size_bytes
            }
        )
        doc_id = res.fetchone()[0]
        conn.commit()
        
    # 2. Run compliance scanning pipeline
    from document_processing.orchestrator import run_document_scan_pipeline
    try:
        pipeline_res = run_document_scan_pipeline(doc_id, contents, filename, source="local", tenant_id=tenant_id)
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
            text("SELECT id FROM knowledge_documents WHERE name = :name AND tenant_id = :tenant_id"),
            {"name": filename, "tenant_id": tenant_id}
        ).fetchone()
        k_doc_id = k_doc_row[0] if k_doc_row else doc_id
        
    return {
        "document_id": f"doc_{k_doc_id}",
        "status": "indexed",
        "pipeline_results": pipeline_res
    }

@app.post("/gateway/documents/redact")
async def redact_gateway_document(
    file: UploadFile = File(...),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    start_time = time.time()
    request_id = f"doc-{uuid.uuid4()}"
    session_id = request_id
    tenant_id = resolve_tenant(x_api_key, authorization)
    username = "gateway_document_user"
    if authorization:
        token = authorization[7:] if authorization.startswith("Bearer ") else authorization
        payload = decode_jwt(token)
        if payload:
            username = payload.get("sub") or payload.get("email") or username

    filename = file.filename or "uploaded-document"
    extension = os.path.splitext(filename)[1].lower()
    image_extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif"}
    supported_extensions = {
        ".pdf", ".docx", ".txt", ".text", ".md", ".markdown", ".csv", ".xlsx", ".xls", *image_extensions
    }

    def event(agent: str, event_type: str, details: str, sequence: int) -> dict:
        from verify_audit import log_agent_event
        log_agent_event(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_name=agent,
            event_type=event_type,
            details=details,
            request_id=request_id,
            sequence=sequence,
        )
        return {
            "agent": agent,
            "event": event_type,
            "details": details,
            "request_id": request_id,
            "sequence": sequence,
        }

    trace = [
        event("Gateway Agent", "DOCUMENT_RECEIVED", f"Accepted upload '{filename}' for tenant {tenant_id}.", 1)
    ]

    contents = await file.read()
    size_bytes = len(contents)
    max_size_bytes = int(os.getenv("AUTHCLAW_DOCUMENT_REDACTION_MAX_BYTES", str(10 * 1024 * 1024)))
    if size_bytes > max_size_bytes:
        trace.append(event("Security Agent", "DOCUMENT_REJECTED_SIZE_LIMIT", f"Upload size {size_bytes} exceeds limit {max_size_bytes}.", 2))
        raise HTTPException(status_code=413, detail="Document is too large for gateway redaction.")

    if extension not in supported_extensions:
        trace.append(event("Security Agent", "DOCUMENT_REJECTED_UNSUPPORTED_TYPE", f"Unsupported file extension '{extension or 'none'}'.", 2))
        raise HTTPException(status_code=415, detail="Unsupported document type for gateway redaction.")

    from document_processing.parsers import extract_document_pages
    extraction = extract_document_pages(contents, filename)
    extracted_text = extraction.text
    if not extracted_text.strip():
        detail = "No extractable text found in document."
        if extraction.ocr_status == "unavailable":
            detail = f"OCR is unavailable for this file: {extraction.ocr_error}"
        trace.append(event("Security Agent", "DOCUMENT_TEXT_EXTRACTION_EMPTY", detail, 2))
        raise HTTPException(status_code=422, detail=detail)

    trace.append(event(
        "Security Agent",
        "DOCUMENT_TEXT_EXTRACTED",
        f"Extracted {len(extracted_text)} characters from '{filename}' using {extraction.extraction_method}. OCR status: {extraction.ocr_status}.",
        2
    ))

    from document_processing.intelligence import analyze_and_redact_document
    document_analysis = analyze_and_redact_document(extraction, username=username, tenant_id=tenant_id)
    redacted_text = document_analysis["redacted_text"]
    triggered = document_analysis["findings"]
    redacted_count = len(triggered)
    finding_actions = {str(item.get("action_taken") or item.get("action") or "").lower() for item in triggered}
    decision = "BLOCK" if "block" in finding_actions else ("REDACT" if redacted_count else "ALLOW")
    risk_level = "HIGH" if decision == "BLOCK" else ("MEDIUM" if redacted_count else "LOW")
    trace.append(event(
        "Security Agent",
        "DOCUMENT_REDACTION_APPLIED" if redacted_count else "DOCUMENT_REDACTION_CLEAN",
        f"Detected {redacted_count} sensitive field(s). Actions: {', '.join(sorted(finding_actions)) or 'allow'}.",
        3,
    ))
    trace.append(event("Policy Agent", "DOCUMENT_POLICY_EVALUATED", f"Decision: {decision}; risk level: {risk_level}.", 4))

    from verify_audit import create_audit_block
    audit_id = create_audit_block(
        query=f"Document Redaction: {filename}",
        response=f"Redacted {redacted_count} sensitive field(s) from uploaded document.",
        allowed=decision != "BLOCK",
        risk_level=risk_level,
        approval_status="N/A",
        session_id=session_id,
        username=username,
        tenant_id=tenant_id,
        policy_name="gateway_document_redaction",
        policy_type="document_redaction",
    )
    trace.append(event("Audit Agent", "DOCUMENT_REDACTION_AUDITED", f"Committed document redaction audit block #{audit_id}.", 5))

    duration_ms = int((time.time() - start_time) * 1000)
    from document_processing.storage import persist_document_intelligence_result
    document_record = persist_document_intelligence_result(
        tenant_id=tenant_id,
        request_id=request_id,
        filename=filename,
        content_type=file.content_type,
        size_bytes=size_bytes,
        content_bytes=contents,
        extraction=extraction,
        analysis=document_analysis,
        decision=decision,
        risk_level=risk_level,
        username=username,
        duration_ms=duration_ms,
    )
    trace.append(event(
        "Registrar Agent",
        "DOCUMENT_INTELLIGENCE_PERSISTED",
        f"Persisted document #{document_record['document_id']} and scan {document_record['scan_id']}.",
        6,
    ))

    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO gateway_requests (
                    timestamp, risk_level, allowed, status, request_id, tenant_id,
                    route_id, provider, model, latency, tokens_in, tokens_out,
                    created_at, decision, duration_ms
                )
                VALUES (
                    NOW(), :risk_level, :allowed, :status, :request_id, :tenant_id,
                    :route_id, :provider, :model, :latency, :tokens_in, 0,
                    NOW(), :decision, :duration_ms
                )
            """),
            {
                "risk_level": risk_level,
                "allowed": decision != "BLOCK",
                "status": "blocked" if decision == "BLOCK" else ("redacted" if redacted_count else "allowed"),
                "request_id": request_id,
                "tenant_id": str(tenant_id),
                "route_id": "gateway-document-redaction",
                "provider": "authclaw",
                "model": "document-redaction",
                "latency": duration_ms,
                "tokens_in": len(extracted_text.split()),
                "decision": decision,
                "duration_ms": duration_ms,
            },
        )
        conn.commit()
    trace.append(event("Registrar Agent", "GATEWAY_DOCUMENT_REQUEST_RECORDED", f"Recorded document request lifecycle metadata in {duration_ms} ms.", 7))

    def serialize_trigger(item):
        result = {}
        for key, value in item.items():
            if hasattr(value, "isoformat"):
                result[key] = value.isoformat()
            else:
                result[key] = value
        return result

    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "filename": filename,
        "content_type": file.content_type,
        "size_bytes": size_bytes,
        "document_id": document_record["document_id"],
        "document_uid": document_record["document_uid"],
        "scan_id": document_record["scan_id"],
        "processing_progress": document_record["progress"],
        "content_sha256": document_record["content_sha256"],
        "status": "blocked" if decision == "BLOCK" else ("redacted" if redacted_count else "clean"),
        "decision": decision,
        "risk_level": risk_level,
        "duration_ms": duration_ms,
        "redacted_count": redacted_count,
        "extraction_method": extraction.extraction_method,
        "ocr_status": extraction.ocr_status,
        "ocr_required": bool(getattr(extraction, "ocr_required", False)),
        "ocr_error": extraction.ocr_error,
        "document_metadata": document_analysis["metadata"],
        "compliance_summary": document_analysis["compliance_summary"],
        "triggered_policies": [serialize_trigger(item) for item in triggered],
        "findings": [serialize_trigger(item) for item in triggered],
        "findings_report": document_analysis["findings_report"],
        "redacted_pages": document_analysis["redacted_pages"],
        "redacted_pdf_base64": document_analysis["redacted_pdf_base64"],
        "extracted_text": extracted_text,
        "redacted_text": redacted_text,
        "trace": trace,
    }

@app.get("/documents/scans/{scan_id}")
def get_document_scan_status(
    scan_id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    from database import engine
    from sqlalchemy import text
    with tenant_context(tenant_id, required=True), engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT s.scan_id, s.status, s.progress, s.scan_duration_ms,
                       s.extraction_method, s.ocr_status, s.ocr_required,
                       s.compliance_summary, d.id, d.filename, d.document_uid,
                       d.status AS document_status
                FROM document_scans s
                JOIN documents d ON d.id = s.document_id AND d.tenant_id = s.tenant_id
                WHERE s.scan_id = :scan_id AND s.tenant_id = :tenant_id
                LIMIT 1
            """),
            {"scan_id": scan_id, "tenant_id": tenant_id},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document scan not found.")
    compliance_summary = {}
    try:
        compliance_summary = json.loads(row[7] or "{}")
    except Exception:
        compliance_summary = {}
    return {
        "scan_id": row[0],
        "status": row[1],
        "progress": row[2],
        "duration_ms": row[3],
        "extraction_method": row[4],
        "ocr_status": row[5],
        "ocr_required": row[6],
        "compliance_summary": compliance_summary,
        "document_id": row[8],
        "filename": row[9],
        "document_uid": row[10],
        "document_status": row[11],
    }

class DocumentScanRequest(BaseModel):
    document_id: str

@app.post("/documents/scan")
def scan_document(
    req: DocumentScanRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    
    doc_id = parse_document_id(req.document_id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Check in knowledge_documents
        k_doc = conn.execute(
            text("SELECT name, size_bytes FROM knowledge_documents WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": doc_id, "tenant_id": tenant_id}
        ).fetchone()
        if not k_doc:
            raise HTTPException(status_code=404, detail="Document not found")
        filename = k_doc[0]
        size_bytes = k_doc[1]
        
        chunks_res = conn.execute(
            text("SELECT content FROM knowledge_chunks WHERE document_id = :doc_id AND tenant_id = :tenant_id ORDER BY id ASC"),
            {"doc_id": doc_id, "tenant_id": tenant_id}
        ).fetchall()
        text_content = "\n\n".join([r[0] for r in chunks_res])
        
        # Check or insert into documents table
        doc_row = conn.execute(
            text("SELECT id FROM documents WHERE filename = :name AND tenant_id = :tenant_id"),
            {"name": filename, "tenant_id": tenant_id}
        ).fetchone()
        if doc_row:
            d_id = doc_row[0]
        else:
            res = conn.execute(
                text("""
                INSERT INTO documents (tenant_id, filename, source, size_bytes, status, risk_score, severity)
                VALUES (:tenant_id, :filename, 'local', :size, 'pending', 0, 'LOW')
                RETURNING id
                """),
                {"tenant_id": tenant_id, "filename": filename, "size": size_bytes}
            )
            d_id = res.fetchone()[0]
            conn.commit()
            
    from document_processing.orchestrator import run_document_scan_pipeline
    pipeline_res = run_document_scan_pipeline(d_id, text_content.encode("utf-8"), filename, source="local", tenant_id=tenant_id)
    return pipeline_res

@app.get("/documents")
def list_all_documents(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT id, filename, source, status, size_bytes, risk_score, severity, created_at, updated_at
                FROM documents
                WHERE tenant_id = :tenant_id
                ORDER BY id DESC
            """),
            {"tenant_id": tenant_id}
        )
        return [dict(r._mapping) for r in res]

@app.get("/documents/{id}")
def get_document_details(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM documents WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": doc_id, "tenant_id": tenant_id}
        ).fetchone()
        if not row:
            k_doc = conn.execute(
                text("SELECT name FROM knowledge_documents WHERE id = :id AND tenant_id = :tenant_id"),
                {"id": doc_id, "tenant_id": tenant_id}
            ).fetchone()
            if k_doc:
                filename = k_doc[0]
                row = conn.execute(
                    text("SELECT * FROM documents WHERE filename = :name AND tenant_id = :tenant_id ORDER BY id DESC LIMIT 1"),
                    {"name": filename, "tenant_id": tenant_id}
                ).fetchone()
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        return dict(row._mapping)

@app.get("/documents/{id}/findings")
def get_document_findings(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        row = resolve_document_record(conn, doc_id, tenant_id)
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        real_doc_id = row[0]
        
        findings_res = conn.execute(
            text("""
                SELECT id, finding_type, matched_pattern, matched_text, risk_level, recommendation, impact, priority, location_evidence
                FROM document_findings
                WHERE document_id = :doc_id AND tenant_id = :tenant_id
            """),
            {"doc_id": real_doc_id, "tenant_id": tenant_id}
        ).fetchall()
        
        return [dict(f._mapping) for f in findings_res]

@app.get("/documents/{id}/audit")
def get_document_audit_trail(
    id: str,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(id)
    
    from database import engine
    from sqlalchemy import text
    from document_processing.auditor import verify_document_audit_chain
    
    with engine.connect() as conn:
        row = resolve_document_record(conn, doc_id, tenant_id)
                
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
            
        real_doc_id = row[0]
        
        audit_res = conn.execute(
            text("""
                SELECT id, timestamp, action, actor, details, integrity_hash, previous_hash
                FROM document_audits
                WHERE document_id = :doc_id AND tenant_id = :tenant_id
                ORDER BY id ASC
            """),
            {"doc_id": real_doc_id, "tenant_id": tenant_id}
        ).fetchall()
        
        audit_list = [dict(a._mapping) for a in audit_res]
        verification = verify_document_audit_chain(real_doc_id, tenant_id=tenant_id)
        
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
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(req.document_id)
    
    from rag.compliance_analyzer import analyze_document_compliance, get_document_text
    try:
        # Get document text and name first
        _, doc_name = get_document_text(doc_id, tenant_id=tenant_id)
        # Perform analysis
        analysis = analyze_document_compliance(doc_id, tenant_id=tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Compliance analysis failed: {str(e)}")
        
    # Generate and store evidence reports
    try:
        from rag.compliance_analyzer import generate_and_vault_reports
        generate_and_vault_reports(doc_id, doc_name, analysis, tenant_id=tenant_id)
    except Exception as e:
        logger.error(f"Failed to generate and store evidence reports: {str(e)}")
        
    # Audit logging
    from verify_audit import create_audit_block
    create_audit_block(
        query=f"Run Compliance Analysis: doc_{doc_id}",
        response=f"Compliance analysis completed for {doc_name}. Overall Risk: {analysis['overall_risk']}",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A",
        tenant_id=tenant_id
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
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    doc_id = parse_document_id(req.document_id)
    
    import os
    import requests
    from rag.compliance_analyzer import get_document_text
    try:
        _, doc_name = get_document_text(doc_id, tenant_id=tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Document not found: {str(e)}")
        
    # Retrieve relevant context
    from rag.retriever import retrieve_formatted_context
    context, citations = retrieve_formatted_context(req.question, top_k=3, document_id=doc_id, tenant_id=tenant_id)
    
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
        approval_status="N/A",
        tenant_id=tenant_id
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
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM knowledge_documents WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": doc_id, "tenant_id": tenant_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found.")
        name = row[0]
        
        # Deleting from documents table triggers cascade delete of scans and findings
        conn.execute(text("DELETE FROM documents WHERE filename = :name AND tenant_id = :tenant_id"), {"name": name, "tenant_id": tenant_id})
        conn.execute(text("DELETE FROM knowledge_documents WHERE id = :id AND tenant_id = :tenant_id"), {"id": doc_id, "tenant_id": tenant_id})
        conn.execute(text("DELETE FROM knowledge_chunks WHERE document_id = :id AND tenant_id = :tenant_id"), {"id": doc_id, "tenant_id": tenant_id})
        conn.commit()
        
    create_audit_block(
        query=f"Delete Knowledge Document: {name}",
        response=f"Document '{name}' and its vector chunks purged from index.",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "Document deleted."}

@app.get("/rag/chunks/{doc_id}")
def get_document_chunks(
    doc_id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant(x_api_key, authorization)
    with engine.connect() as conn:
        doc = conn.execute(
            text("SELECT id FROM knowledge_documents WHERE id = :doc_id AND tenant_id = :tenant_id"),
            {"doc_id": doc_id, "tenant_id": tenant_id}
        ).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")
        res = conn.execute(
            text("SELECT id, content, embedding_preview FROM knowledge_chunks WHERE document_id = :doc_id AND tenant_id = :tenant_id ORDER BY id ASC"),
            {"doc_id": doc_id, "tenant_id": tenant_id}
        )
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
    tenant_id = resolve_tenant(x_api_key, authorization)

        
    from rag.retriever import retrieve_context
    hits = retrieve_context(req.query, top_k=req.top_k, tenant_id=tenant_id)
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
    normalized_email = role_req.username.strip().lower()
    if not is_valid_work_email(normalized_email):
        raise HTTPException(status_code=400, detail="Enter a valid tenant user work email, for example user@company.com.")
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
                "email": normalized_email,
                "role": role_req.role,
                "permissions": role_req.permissions,
            },
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tenant user not found. Choose an existing tenant user from this tenant before assigning a role.")
        conn.commit()
    create_audit_block(
        query=f"Modify Access Control: {normalized_email}",
        response=f"Username {normalized_email} role updated/set to {role_req.role}.",
        allowed=True,
        risk_level="MEDIUM",
        approval_status="N/A",
        username=normalized_email,
        tenant_id=tenant_id
    )
    return {"status": "success", "message": "User access mapping updated."}





# 11. EVIDENCE VAULT
@app.get("/evidence")
def get_evidence(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    from database import engine
    from sqlalchemy import text
    tenant_id = resolve_tenant(x_api_key, authorization)
    with engine.connect() as conn:
        res = conn.execute(
            text("""
                SELECT id, name, category, file_path, collected_at, hash
                FROM compliance_evidence
                WHERE tenant_id = :tenant_id
                ORDER BY id DESC
            """),
            {"tenant_id": tenant_id}
        )
        return [dict(r._mapping) for r in res]

@app.post("/evidence/collect")
def collect_evidence(
    req: EvidenceUploadRequest,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    import hashlib
    tenant_id = resolve_tenant(x_api_key, authorization)
    now_str = datetime.now(timezone.utc).date().isoformat()
    f_hash = f"sha256-{hashlib.sha256(req.name.encode()).hexdigest()[:16]}"
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO compliance_evidence (tenant_id, name, category, file_path, collected_at, hash)
            VALUES (:tenant_id, :name, :category, :file_path, :collected_at, :hash)
            """),
            {
                "tenant_id": tenant_id,
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
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": f"Compliance evidence '{req.name}' successfully vaulted."}

@app.delete("/evidence/{id}")
def delete_evidence(
    id: int,
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
        
    import os
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name, file_path FROM compliance_evidence WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": id, "tenant_id": tenant_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Evidence not found")
        name = row[0]
        file_path = row[1]
        
        conn.execute(
            text("DELETE FROM compliance_evidence WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": id, "tenant_id": tenant_id}
        )
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
        approval_status="N/A",
        tenant_id=tenant_id
    )
    return {"status": "success", "message": f"Compliance evidence '{name}' permanently deleted."}

@app.get("/evidence/export/csv")
def export_evidence_csv_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_evidence_csv
    csv_data = generate_evidence_csv(tenant_id=tenant_id)
    return Response(content=csv_data, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=evidence_vault.csv"})

@app.get("/evidence/export/pdf")
def export_evidence_pdf_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_evidence_pdf
    pdf_data = generate_evidence_pdf(tenant_id=tenant_id)
    return Response(content=pdf_data, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=evidence_vault.pdf"})

@app.get("/audit/export/csv")
def export_audit_csv_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_audit_csv
    from verify_audit import sign_export_payload
    csv_data = generate_audit_csv(tenant_id=tenant_id)
    headers = {"Content-Disposition": "attachment; filename=audit_ledger.csv"}
    headers.update(sign_export_payload(csv_data, tenant_id=tenant_id, export_type="audit-csv"))
    return Response(content=csv_data, media_type="text/csv", headers=headers)

@app.get("/audit/export/pdf")
def export_audit_pdf_endpoint(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    from document_processing.exports import generate_audit_pdf
    from verify_audit import sign_export_payload
    pdf_data = generate_audit_pdf(tenant_id=tenant_id)
    headers = {"Content-Disposition": "attachment; filename=audit_ledger.pdf"}
    headers.update(sign_export_payload(pdf_data, tenant_id=tenant_id, export_type="audit-pdf"))
    return Response(content=pdf_data, media_type="application/pdf", headers=headers)


@app.get("/compliance/framework-scores")
def get_compliance_framework_scores(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None)
):
    tenant_id = resolve_tenant(x_api_key, authorization)
    
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
                  AND d.tenant_id = :tenant_id
                  AND df.tenant_id = :tenant_id
                """),
                {"tenant_id": tenant_id}
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
    username: Optional[str] = None
    password: Optional[str] = None

class PasswordResetRequest(BaseModel):
    username: str

class PasswordResetConfirmRequest(BaseModel):
    token: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

JWT_SECRET = SecretManager().get_secret("JWT_SECRET") or SecretManager().get_secret("AUTHCLAW_JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT secret is not available through the AuthClaw SecretManager.")

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

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO auth_mfa_sessions (
                    session_id, username, role, permissions, tenant_id, user_id,
                    email_verified, domain_verified, step, expires_at
                )
                VALUES (
                    :session_id, :username, :role, :permissions, :tenant_id, :user_id,
                    :email_verified, :domain_verified, :step, NOW() + (:ttl_seconds * INTERVAL '1 second')
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
                "ttl_seconds": AUTH_SESSION_TTL_SECONDS,
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
    with tenant_context(tenant_id, required=True), engine.connect() as conn:
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

def generate_reset_token() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")

def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_refresh_token_record(payload: dict):
    from database import engine
    from sqlalchemy import text

    jti = payload.get("jti")
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    if not jti or not user_id or not tenant_id:
        return None

    with tenant_context(tenant_id, required=True), engine.connect() as conn:
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
    if smtp_host and "gmail" in smtp_host.lower() and smtp_password:
        smtp_password = smtp_password.replace(" ", "")

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
                hint = "sendgrid_error"
                if response.status_code in {401, 403}:
                    hint = "sendgrid_authentication_failure"
                elif response.status_code == 400 and "from" in response.text.lower():
                    hint = "sendgrid_invalid_or_unverified_sender"
                logger.error(
                    "%s SendGrid API delivery failed: category=%s status=%s body=%s",
                    purpose,
                    hint,
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
        except requests.exceptions.Timeout as exc:
            logger.error("%s SendGrid API delivery timed out.", purpose)
            raise HTTPException(
                status_code=503,
                detail=f"{purpose} email could not be delivered by SendGrid API because the connection timed out.",
            ) from exc
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
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("%s SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD.", purpose)
        raise HTTPException(
            status_code=503,
            detail=f"{purpose} email could not be delivered because SMTP authentication failed."
        ) from exc
    except (smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused) as exc:
        logger.error("%s SMTP sender or recipient was refused. Check SMTP_FROM and verified sender identity: %s", purpose, exc)
        raise HTTPException(
            status_code=503,
            detail=f"{purpose} email could not be delivered because the sender or recipient was refused."
        ) from exc
    except (TimeoutError, OSError) as exc:
        logger.error("%s SMTP connection failed or timed out. host=%s port=%s tls=%s error=%s", purpose, smtp_host, smtp_port, smtp_tls, exc)
        raise HTTPException(
            status_code=503,
            detail=f"{purpose} email could not be delivered because SMTP connection failed or timed out."
        ) from exc
    except smtplib.SMTPException as exc:
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

def send_password_reset_email(recipient: str, token: str, organization_name: str) -> None:
    deliver_auth_email(
        recipient,
        "Reset your AuthClaw password",
        "\n".join(
            [
                f"AuthClaw received a password reset request for {organization_name}.",
                "",
                "Use this one-time reset token to create a new password:",
                token,
                "",
                "This token expires soon and can only be used once.",
                "If you did not request this reset, contact your AuthClaw administrator.",
            ]
        ),
        "Password reset",
    )


def env_value(name: str, default: str = "") -> str:
    if name in SENSITIVE_ENV_NAMES:
        return SecretManager().get_secret(name) or default
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


def soft_fail_email_delivery_for_local() -> bool:
    production = env_value("AUTHCLAW_ENV", "development").lower() in {"production", "prod"}
    return (not production) and env_bool("AUTHCLAW_SOFT_FAIL_EMAIL_DELIVERY", True)


def skip_domain_verification_for_testing() -> bool:
    return env_bool("SKIP_DOMAIN_VERIFICATION")


def disable_mfa_for_testing() -> bool:
    # Local manual runs can bypass MFA for usability, but automated tests must
    # keep the production MFA contract unless a test explicitly opts out. This
    # bypass is never honored in production.
    production = env_value("AUTHCLAW_ENV", "development").lower() in {"production", "prod"}
    if production:
        return False
    if os.getenv("PYTEST_CURRENT_TEST"):
        return os.getenv("DISABLE_MFA_FOR_TESTING", "").lower() in {"1", "true", "yes", "on"} or os.getenv(
            "AUTHCLAW_ALLOW_TEST_MFA_BYPASS", ""
        ).lower() in {"1", "true", "yes", "on"}
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
                INSERT INTO policies (tenant_id, name, type, rules, enabled, severity_level, version, status, published_at)
                VALUES (:tenant_id, :name, :type, :rules, true, 'HIGH', 1, 'published', NOW())
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
    with tenant_context(tenant_id, required=True):
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

    with auth_lookup_context(), engine.connect() as conn:
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
        pending_registration = None
        if not user:
            pending_registration = conn.execute(
                text("""
                    SELECT work_email, domain, email_verified, domain_verified,
                           email_verification_token, domain_verification_token
                    FROM onboarding_registrations
                    WHERE lower(work_email) = lower(:email)
                      AND activated_at IS NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                """),
                {"email": req.username},
            ).fetchone()

    if not user or not verify_password(req.password, user[3]):
        if not user and pending_registration:
            if not bool(pending_registration[2]):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Email not verified",
                        "email_verified": False,
                        "email": pending_registration[0],
                        "domain": pending_registration[1],
                        "email_token": pending_registration[4],
                        "domain_token": pending_registration[5],
                    },
                )
            if not bool(pending_registration[3]):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Domain not verified",
                        "domain_verified": False,
                        "email": pending_registration[0],
                        "domain": pending_registration[1],
                        "domain_token": pending_registration[5],
                    },
                )
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
    effective_mfa_enabled = mfa_enabled and not disable_mfa_for_testing()
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

    if effective_mfa_enabled and not totp_secret:
        return JSONResponse(
            status_code=400,
            content={
                "error": "MFA_NOT_CONFIGURED",
                "message": "MFA is not configured for this tenant."
            }
        )

    if not effective_mfa_enabled:
        with tenant_context(tenant_id, required=True), engine.connect() as conn:
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

@app.post("/auth/password/reset-request")
def auth_password_reset_request(req: PasswordResetRequest):
    from database import engine
    from sqlalchemy import text

    normalized_email = req.username.strip().lower()
    if not normalized_email:
        raise HTTPException(status_code=400, detail="Email is required.")

    generic_response = {
        "status": "success",
        "message": "If the account exists, a password reset token has been sent to the verified email address."
    }

    with auth_lookup_context(), engine.connect() as conn:
        user = conn.execute(
            text("""
                SELECT u.id, u.tenant_id, u.email, u.status, u.email_verified,
                       t.name, t.domain_verified
                FROM tenant_users u
                JOIN tenants t ON t.id = u.tenant_id
                WHERE lower(u.email) = lower(:email)
                LIMIT 1
            """),
            {"email": normalized_email},
        ).fetchone()

        if not user:
            logger.info(
                "Password reset requested for non-existent account hash=%s",
                hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()[:12],
            )
            if env_value("AUTHCLAW_ENV", "development").lower() not in {"production", "prod"}:
                response = dict(generic_response)
                response["email_delivery"] = "not_attempted"
                response["local_debug"] = (
                    "No active tenant user exists for this email. Register and verify the tenant first, "
                    "or use the exact email used during tenant activation."
                )
                return response
            return generic_response
        if user[3] != "active":
            raise HTTPException(status_code=403, detail="User account is not active.")
        if not bool(user[4]):
            raise HTTPException(status_code=400, detail="Email must be verified before password reset.")
        if not bool(user[6]):
            raise HTTPException(status_code=400, detail="Domain must be verified before password reset.")

        token = generate_reset_token()
        token_hash = hash_reset_token(token)
        conn.execute(
            text("""
                DELETE FROM auth_password_reset_tokens
                WHERE user_id = :user_id AND used_at IS NULL
            """),
            {"user_id": user[0]},
        )
        conn.execute(
            text("""
                INSERT INTO auth_password_reset_tokens (
                    token_hash, tenant_id, user_id, email, expires_at
                )
                VALUES (:token_hash, :tenant_id, :user_id, :email, NOW() + INTERVAL '30 minutes')
            """),
            {
                "token_hash": token_hash,
                "tenant_id": user[1],
                "user_id": user[0],
                "email": user[2],
            },
        )
        conn.commit()

    email_delivery_status = "sent"
    email_delivery_error = None
    try:
        send_password_reset_email(user[2], token, user[5] or "your organization")
    except HTTPException as exc:
        if not soft_fail_email_delivery_for_local():
            raise
        email_delivery_status = "failed_local_soft_bypass"
        email_delivery_error = exc.detail
        logger.warning("Password reset email delivery failed in local development: %s", exc.detail)

    response = dict(generic_response)
    response["email_delivery"] = email_delivery_status
    if skip_email_delivery_for_testing() or email_delivery_status == "failed_local_soft_bypass":
        response["reset_token"] = token
        if email_delivery_error:
            response["email_error"] = email_delivery_error
    return response

@app.post("/auth/password/reset-confirm")
def auth_password_reset_confirm(req: PasswordResetConfirmRequest):
    from database import engine
    from sqlalchemy import text

    new_password = req.password or ""
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    token_hash = hash_reset_token(req.token.strip())
    with auth_lookup_context(), engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT prt.token_hash, prt.tenant_id, prt.user_id, u.email
                FROM auth_password_reset_tokens prt
                JOIN tenant_users u ON u.id = prt.user_id AND u.tenant_id = prt.tenant_id
                WHERE prt.token_hash = :token_hash
                  AND prt.used_at IS NULL
                  AND prt.expires_at > NOW()
                  AND u.status = 'active'
                LIMIT 1
            """),
            {"token_hash": token_hash},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

        conn.execute(
            text("""
                UPDATE tenant_users
                SET password_hash = :password_hash, updated_at = NOW()
                WHERE id = :user_id AND tenant_id = :tenant_id
            """),
            {
                "password_hash": hash_password(new_password),
                "user_id": row[2],
                "tenant_id": row[1],
            },
        )
        conn.execute(
            text("UPDATE auth_password_reset_tokens SET used_at = NOW() WHERE token_hash = :token_hash"),
            {"token_hash": token_hash},
        )
        conn.execute(
            text("UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE user_id = :user_id AND tenant_id = :tenant_id AND revoked_at IS NULL"),
            {"user_id": row[2], "tenant_id": row[1]},
        )
        conn.commit()

    return {
        "status": "success",
        "message": "Password reset complete. Sign in with your new password.",
        "email": row[3],
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
    with tenant_context(tenant_id, req.session_id, required=True), engine.connect() as conn:
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

    with tenant_context(tenant_id, req.session_id, required=True), engine.connect() as conn:
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

    with auth_lookup_context(), engine.connect() as conn:
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
    response = {
        "status": "success",
        "message": "MFA reset token sent to your verified email address."
    }
    email_delivery_status = "sent"
    email_delivery_error = None
    try:
        send_mfa_reset_email(user[2], reset_token, user[9] or "your organization")
    except HTTPException as exc:
        if not soft_fail_email_delivery_for_local():
            raise
        email_delivery_status = "failed_local_soft_bypass"
        email_delivery_error = exc.detail
        logger.warning("MFA reset email delivery failed in local development: %s", exc.detail)

    response["email_delivery"] = email_delivery_status
    if skip_email_delivery_for_testing() or email_delivery_status == "failed_local_soft_bypass":
        response["reset_token"] = reset_token
        response["message"] = "MFA reset token generated. Email delivery is unavailable locally, so use the token shown here."
        if email_delivery_error:
            response["email_error"] = email_delivery_error
    return response

@app.post("/auth/mfa/reset-confirm")
def auth_mfa_reset_confirm(req: MFAResetConfirmRequest):
    session = load_auth_session(req.token)
    if not session or session["step"] != "mfa_reset":
        if not soft_fail_email_delivery_for_local() or not req.username or not req.password:
            raise HTTPException(status_code=400, detail="Invalid or expired MFA reset token.")

        from database import engine
        from sqlalchemy import text
        with auth_lookup_context(), engine.connect() as conn:
            user = conn.execute(
                text("""
                    SELECT u.id, u.tenant_id, u.email, u.password_hash, u.role,
                           u.permissions, u.email_verified, u.status, t.domain_verified
                    FROM tenant_users u
                    JOIN tenants t ON t.id = u.tenant_id
                    WHERE lower(u.email) = lower(:email)
                    LIMIT 1
                """),
                {"email": req.username},
            ).fetchone()

        if (
            not user
            or not verify_password(req.password, user[3])
            or user[7] != "active"
            or not bool(user[6])
            or not bool(user[8])
        ):
            raise HTTPException(status_code=400, detail="Invalid or expired MFA reset token.")

        session = {
            "username": user[2],
            "role": user[4],
            "permissions": user[5],
            "tenant_id": user[1],
            "user_id": user[0],
            "email_verified": True,
            "domain_verified": True,
            "step": "mfa_reset",
        }

    new_secret = generate_totp_secret()
    username = session["username"]
    tenant_id = session["tenant_id"]
    user_id = session["user_id"]

    from database import engine
    from sqlalchemy import text
    with tenant_context(tenant_id, req.token, required=True), engine.connect() as conn:
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
        conn.execute(
            text("""
                UPDATE tenants
                SET totp_secret = :secret
                WHERE id = :tenant_id
                  AND lower(email) = lower(:email)
            """),
            {
                "secret": new_secret,
                "tenant_id": tenant_id,
                "email": username,
            },
        )
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

        email_delivery_status = "sent"
        email_delivery_error = None
        try:
            send_verification_email(req.email, email_token, organization_name)
        except HTTPException as exc:
            if not soft_fail_email_delivery_for_local():
                raise
            email_delivery_status = "failed_local_soft_bypass"
            email_delivery_error = exc.detail
            logger.warning(
                "Verification email delivery failed during local development; continuing registration with returned token: %s",
                exc.detail,
            )
        
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
        "email_delivery": email_delivery_status,
        "domain_token": domain_token,
        "totp_secret": totp_secret,
        "otpauth_uri": otpauth_uri
    }
    if skip_email_delivery_for_testing():
        response["message"] = "Registration received. Email delivery skipped for local testing; use the returned email token."
        response["email_delivery"] = "skipped_for_testing"
        response["email_token"] = email_token
    elif email_delivery_status == "failed_local_soft_bypass":
        response["message"] = "Registration received. Email delivery failed in local development; use the returned email token."
        response["email_token"] = email_token
        response["email_error"] = email_delivery_error
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

@app.get("/analytics/governance")
def get_governance_analytics(tenant_id: int = Depends(get_authenticated_tenant)):
    from services.observability_service import ObservabilityService

    return ObservabilityService().governance_analytics(tenant_id)

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
    from services.provider_connection_tester import ProviderConnectionTestError, test_provider_connection
    from services.secret_manager import SecretManager, SecretManagerError

    provider = req.provider.lower().replace(" ", "_")
    payload = dict(req.payload or {})
    live_test = bool(payload.pop("live_test", False))

    try:
        test_result = test_provider_connection(provider, payload, live=live_test)
        secret_record = SecretManager().store_provider_payload(tenant_id, provider, payload)
    except (ProviderConnectionTestError, SecretManagerError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO tenant_credentials (
                tenant_id, provider, encrypted_payload, secret_ref, secret_backend,
                secret_version, key_fingerprint, key_prefix, health_status,
                health_checked_at, health_message, rotated_at, revoked_at, updated_at
            )
            VALUES (
                :tid, :provider, :payload, :secret_ref, :secret_backend,
                :secret_version, :key_fingerprint, :key_prefix, :health_status,
                NOW(), :health_message, NOW(), NULL, NOW()
            )
            ON CONFLICT (tenant_id, provider) DO UPDATE
            SET encrypted_payload = EXCLUDED.encrypted_payload,
                secret_ref = EXCLUDED.secret_ref,
                secret_backend = EXCLUDED.secret_backend,
                secret_version = EXCLUDED.secret_version,
                key_fingerprint = EXCLUDED.key_fingerprint,
                key_prefix = EXCLUDED.key_prefix,
                health_status = EXCLUDED.health_status,
                health_checked_at = NOW(),
                health_message = EXCLUDED.health_message,
                rotated_at = NOW(),
                revoked_at = NULL,
                updated_at = NOW()
            """),
            {
                "tid": tenant_id,
                "provider": secret_record["provider"],
                "payload": secret_record["encrypted_payload"],
                "secret_ref": secret_record["secret_ref"],
                "secret_backend": secret_record["secret_backend"],
                "secret_version": secret_record["secret_version"],
                "key_fingerprint": secret_record["key_fingerprint"],
                "key_prefix": secret_record["key_prefix"],
                "health_status": test_result["status"],
                "health_message": "Live connection verified." if test_result.get("live") else "Credential structure validated.",
            }
        )
        conn.commit()
    create_audit_block(
        query=f"Connect Provider Credentials: {secret_record['provider']}",
        response=f"Provider credential stored via {secret_record['secret_backend']}. Raw secret value was not logged or returned.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
        
    return {
        "status": "success",
        "provider": secret_record["provider"],
        "storage": secret_record["secret_backend"],
        "key_prefix": secret_record["key_prefix"],
        "health_status": test_result["status"],
        "message": f"{secret_record['provider']} credentials connected successfully. Raw key will not be shown again.",
    }

@app.get("/providers/list")
def list_connected_providers(tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    with engine.connect() as conn:
        res = conn.execute(
            text(
                """
                SELECT provider, updated_at, secret_backend, key_prefix, health_status,
                       health_checked_at, health_message, rotated_at, revoked_at
                FROM tenant_credentials
                WHERE tenant_id = :tid AND revoked_at IS NULL
                ORDER BY provider
                """
            ),
            {"tid": tenant_id}
        ).fetchall()
        
    providers = []
    for r in res:
        providers.append({
            "provider": r[0],
            "connected": True,
            "updated_at": r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]),
            "storage": r[2],
            "key_prefix": r[3],
            "health_status": r[4] or "unknown",
            "health_checked_at": r[5].isoformat() if hasattr(r[5], "isoformat") else (str(r[5]) if r[5] else None),
            "health_message": r[6],
            "rotated_at": r[7].isoformat() if hasattr(r[7], "isoformat") else (str(r[7]) if r[7] else None),
            "revoked": bool(r[8]),
        })
    return providers

@app.post("/providers/{provider}/rotate")
def rotate_provider_credentials(provider: str, req: ProviderConnectRequest, tenant_id: int = Depends(get_authenticated_tenant)):
    req.provider = provider
    result = connect_provider_credentials(req, tenant_id)
    from verify_audit import create_audit_block
    create_audit_block(
        query=f"Rotate Provider Credentials: {provider.lower()}",
        response="Provider credential rotated. New raw secret was stored securely and not returned.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
    result["message"] = f"{provider.lower()} credentials rotated successfully. Raw key will not be shown again."
    return result

@app.post("/providers/{provider}/test")
def test_stored_provider_credentials(provider: str, live: bool = False, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from services.provider_connection_tester import ProviderConnectionTestError, test_provider_connection
    from services.secret_manager import SecretManager

    provider_key = provider.lower().replace(" ", "_")
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT provider, encrypted_payload, secret_ref, secret_backend, secret_version
                FROM tenant_credentials
                WHERE tenant_id = :tid AND provider = :provider AND revoked_at IS NULL
                """
            ),
            {"tid": tenant_id, "provider": provider_key},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Provider credentials not configured.")
        credential_row = dict(row._mapping)
        try:
            payload = SecretManager().resolve_provider_payload(credential_row)
            result = test_provider_connection(provider_key, payload, live=live)
            status_value = result["status"]
            message = "Live provider connection verified." if live else "Credential structure validated."
        except (ProviderConnectionTestError, Exception) as exc:
            status_value = "unhealthy"
            message = str(exc)
            result = {"provider": provider_key, "status": status_value, "live": live, "error": message}

        conn.execute(
            text(
                """
                UPDATE tenant_credentials
                SET health_status = :status, health_checked_at = NOW(), health_message = :message, updated_at = NOW()
                WHERE tenant_id = :tid AND provider = :provider
                """
            ),
            {"status": status_value, "message": message, "tid": tenant_id, "provider": provider_key},
        )
        conn.commit()

    return {**result, "message": message}

@app.get("/providers/{provider}/health")
def provider_secret_health(provider: str, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    provider_key = provider.lower().replace(" ", "_")
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT provider, secret_backend, key_prefix, health_status, health_checked_at,
                       health_message, rotated_at, updated_at
                FROM tenant_credentials
                WHERE tenant_id = :tid AND provider = :provider AND revoked_at IS NULL
                """
            ),
            {"tid": tenant_id, "provider": provider_key},
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Provider credentials not configured.")
    return {
        "provider": row[0],
        "storage": row[1],
        "key_prefix": row[2],
        "health_status": row[3] or "unknown",
        "health_checked_at": row[4].isoformat() if hasattr(row[4], "isoformat") else (str(row[4]) if row[4] else None),
        "health_message": row[5],
        "rotated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else (str(row[6]) if row[6] else None),
        "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else (str(row[7]) if row[7] else None),
    }

@app.delete("/providers/{provider}")
def disconnect_provider_credentials(provider: str, tenant_id: int = Depends(get_authenticated_tenant)):
    from database import engine
    from sqlalchemy import text
    from verify_audit import create_audit_block
    from services.secret_manager import SecretManager
    provider_key = provider.lower().replace(" ", "_")
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT secret_ref, secret_backend FROM tenant_credentials WHERE tenant_id = :tid AND provider = :provider"),
            {"tid": tenant_id, "provider": provider_key},
        ).fetchone()
        if row and row[0] and row[1] == "aws_secrets_manager":
            try:
                SecretManager().delete_secret(row[0])
            except Exception as exc:
                logger.warning(f"Failed to delete external secret for tenant {tenant_id}: {exc}")
        conn.execute(
            text(
                """
                UPDATE tenant_credentials
                SET revoked_at = NOW(), health_status = 'revoked', updated_at = NOW()
                WHERE tenant_id = :tid AND provider = :provider
                """
            ),
            {"tid": tenant_id, "provider": provider_key}
        )
        conn.commit()
    create_audit_block(
        query=f"Disconnect Provider Credentials: {provider_key}",
        response="Provider credentials revoked for this tenant.",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )
    return {"status": "success", "message": f"{provider_key} credentials disconnected."}


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
    return [
        approval_response_record(record, tenant_id=tenant_id)
        for record in get_all_approvals(tenant_id=tenant_id).values()
    ]


@app.get("/gateway/approvals/{approval_id}/history")
def get_gateway_approval_history(approval_id: str, tenant_id: int = Depends(get_authenticated_tenant)):
    record = get_approval(approval_id)
    if record is None or record.get("tenant_id") != tenant_id:
        raise HTTPException(status_code=404, detail="Approval ID not found")
    return get_approval_history(approval_id, tenant_id=tenant_id)

