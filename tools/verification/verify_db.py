from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    for session in ['verify_test_01', 'verify_test_02']:
        rows = conn.execute(
            text("SELECT role, SUBSTRING(content, 1, 70) FROM chat_messages WHERE session_id=:s ORDER BY id ASC"),
            {"s": session}
        ).fetchall()
        print(f"Session: {session} ({len(rows)} messages)")
        for r in rows:
            print(f"  [{r[0]:10}] {r[1]}")
        print()
