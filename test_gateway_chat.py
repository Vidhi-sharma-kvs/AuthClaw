import hashlib
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import API_KEY, app


client = TestClient(app)
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}


def _tenant_id_for_test_key():
    key_hash = hashlib.sha256(API_KEY.encode("utf-8")).hexdigest()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM tenant_api_keys WHERE key_hash = :hash"),
            {"hash": key_hash},
        ).scalar()


def test_gateway_chat_tracks_request_audit_trace_and_tenant():
    session_id = f"gateway-phase1-{uuid.uuid4().hex}"

    response = client.post(
        "/gateway/chat",
        headers=headers,
        json={
            "session_id": session_id,
            "message": "What is GDPR?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["request_id"].startswith("req-")
    assert isinstance(data["trace"], list)
    assert len(data["trace"]) > 0

    request_id = data["request_id"]
    tenant_id = _tenant_id_for_test_key()

    with engine.connect() as conn:
        gateway_row = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, status, created_at
                FROM gateway_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": request_id},
        ).fetchone()
        trace_count = conn.execute(
            text("SELECT COUNT(*) FROM agent_events WHERE request_id = :request_id"),
            {"request_id": request_id},
        ).scalar()

    assert gateway_row is not None
    assert gateway_row.request_id == request_id
    assert gateway_row.tenant_id == str(tenant_id)
    assert gateway_row.status == "allowed"
    assert gateway_row.created_at is not None
    assert trace_count > 0


def test_existing_chat_route_still_works():
    response = client.post(
        "/chat",
        headers=headers,
        json={
            "session_id": f"compat-chat-{uuid.uuid4().hex}",
            "message": "What is GDPR?",
        },
    )

    assert response.status_code == 200
    assert "response" in response.json()


def test_existing_openai_compatible_route_still_works():
    response = client.post(
        "/v1/chat/completions",
        headers=headers,
        json={
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "What is GDPR?"},
            ],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert data["choices"][0]["message"]["content"]
