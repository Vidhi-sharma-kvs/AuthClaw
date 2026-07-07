import json
from database import engine
from sqlalchemy import text
from services.tenant_context import get_current_tenant_id


PROVIDER_UNAVAILABLE_COPY = (
    "The configured model provider is currently unavailable. AuthClaw completed "
    "the security, policy, and audit checks, but the upstream model call could "
    "not be completed. Check the Providers page, API credentials, and outbound "
    "network access, then try again."
)


def sanitize_provider_message(content):
    text_content = str(content or "")
    provider_error_markers = (
        "[Offline Fallback]",
        "Provider unavailable:",
        "HTTPSConnectionPool",
        "generativelanguage.googleapis.com",
        "Max retries exceeded",
        "Failed to establish a new connection",
        "key=",
    )
    if any(marker in text_content for marker in provider_error_markers):
        return PROVIDER_UNAVAILABLE_COPY
    return content


def sanitize_trace(trace):
    if not isinstance(trace, list):
        return trace
    sanitized = []
    for item in trace:
        if isinstance(item, dict):
            clean_item = dict(item)
            if "details" in clean_item:
                clean_item["details"] = sanitize_provider_message(clean_item["details"])
            sanitized.append(clean_item)
        else:
            sanitized.append(item)
    return sanitized


def ensure_session_exists(session_id: str, tenant_id=None):
    """
    Ensures that a chat session exists in the database.
    """
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT id FROM chat_sessions WHERE session_id = :session_id"),
                {"session_id": session_id}
            ).fetchone()
            if not res:
                if tenant_id is not None:
                    conn.execute(
                        text(
                            """
                            INSERT INTO chat_sessions (session_id, title, user_id, tenant_id)
                            VALUES (:session_id, 'New Chat', 'admin_user', :tenant_id)
                            """
                        ),
                        {"session_id": session_id, "tenant_id": int(tenant_id)}
                    )
                else:
                    conn.execute(
                        text("INSERT INTO chat_sessions (session_id, title, user_id) VALUES (:session_id, 'New Chat', 'admin_user')"),
                        {"session_id": session_id}
                    )
                conn.commit()
    except Exception as e:
        import logging
        logger = logging.getLogger("authclaw.memory")
        logger.error(f"Database error in ensure_session_exists: {e}", exc_info=True)


def add_message(session_id, role, content, trace=None):
    try:
        tenant_id = get_current_tenant_id()
        ensure_session_exists(session_id, tenant_id=tenant_id)
        with engine.connect() as conn:
            if tenant_id is not None:
                conn.execute(
                    text(
                        """
                        INSERT INTO chat_messages (session_id, role, content, trace, tenant_id)
                        VALUES (:session_id, :role, :content, :trace, :tenant_id)
                        """
                    ),
                    {
                        "session_id": session_id,
                        "role": role,
                        "content": content,
                        "trace": trace,
                        "tenant_id": int(tenant_id),
                    }
                )
            else:
                conn.execute(
                    text("INSERT INTO chat_messages (session_id, role, content, trace) VALUES (:session_id, :role, :content, :trace)"),
                    {"session_id": session_id, "role": role, "content": content, "trace": trace}
                )
            conn.execute(
                text("UPDATE chat_sessions SET updated_at = NOW() WHERE session_id = :session_id"),
                {"session_id": session_id}
            )
            conn.commit()
    except Exception as e:
        import logging
        logger = logging.getLogger("authclaw.memory")
        logger.error(f"Database error in add_message: {e}", exc_info=True)


def get_history(session_id):
    try:
        with engine.connect() as conn:
            res = conn.execute(
                text("SELECT role, content, trace FROM chat_messages WHERE session_id = :session_id ORDER BY id ASC"),
                {"session_id": session_id}
            )
            history = []
            for row in res:
                role = row[0]
                content = row[1]
                trace = row[2]
                
                # Reconstruct extra keys from JSON strings for blocked/system messages if stored as JSON
                msg = {"role": role}
                if role in ("blocked", "system"):
                    try:
                        parsed = json.loads(content)
                        if isinstance(parsed, dict):
                            msg.update(parsed)
                        else:
                            msg["content"] = content
                    except Exception:
                        msg["content"] = content
                else:
                    msg["content"] = sanitize_provider_message(content)
                    
                if trace:
                    try:
                        msg["trace"] = sanitize_trace(json.loads(trace))
                    except Exception:
                        msg["trace"] = sanitize_provider_message(trace)
                    
                history.append(msg)
            return history
    except Exception as e:
        import logging
        logger = logging.getLogger("authclaw.memory")
        logger.error(f"Database error in get_history: {e}", exc_info=True)
        return []
