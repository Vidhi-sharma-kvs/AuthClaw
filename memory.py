import json
from database import engine
from sqlalchemy import text


def ensure_session_exists(session_id: str):
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
        ensure_session_exists(session_id)
        with engine.connect() as conn:
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
                    msg["content"] = content
                    
                if trace:
                    try:
                        msg["trace"] = json.loads(trace)
                    except Exception:
                        msg["trace"] = trace
                    
                history.append(msg)
            return history
    except Exception as e:
        import logging
        logger = logging.getLogger("authclaw.memory")
        logger.error(f"Database error in get_history: {e}", exc_info=True)
        return []