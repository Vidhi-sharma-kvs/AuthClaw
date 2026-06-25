from database import engine
from sqlalchemy import text

with engine.connect() as conn:
    rows = conn.execute(
        text("SELECT session_id, role, SUBSTRING(content, 1, 100) FROM chat_messages WHERE session_id='trace_test_001' ORDER BY id ASC")
    ).fetchall()
    print(f"Messages in trace_test_001 session ({len(rows)} total):")
    for r in rows:
        print(f"  [{r[1]:10}] {r[2]}")
