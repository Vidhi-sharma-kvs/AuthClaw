import hashlib
import uuid
import time
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import text

import conftest
from approval_store import create_approval, get_approval
from database import engine
from main import API_KEY, app, create_jwt, get_hotp_token
from services.gateway_service import GatewayService


client = TestClient(app)
token = create_jwt(
    {
        "sub": conftest.tenant_email,
        "email": conftest.tenant_email,
        "tenant_id": conftest.tenant_id,
        "role": "Super Admin",
    }
)
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}",
}


def _tenant_id_for_test_key():
    key_hash = hashlib.sha256(API_KEY.encode("utf-8")).hexdigest()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM tenant_api_keys WHERE key_hash = :hash"),
            {"hash": key_hash},
        ).scalar()


def _mfa_code(offset: int = 0) -> str:
    return get_hotp_token(conftest.totp_secret, int(time.time()) // 30 + offset)


def test_gateway_lifecycle_writes_route_decision_audit_and_trace():
    session_id = f"gateway-lifecycle-{uuid.uuid4().hex}"

    response = client.post(
        "/gateway/chat",
        headers=headers,
        json={"session_id": session_id, "message": "What is SOC2?"},
    )

    assert response.status_code == 200
    payload = response.json()
    request_id = payload["request_id"]
    tenant_id = _tenant_id_for_test_key()

    with engine.connect() as conn:
        gateway_row = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, provider, model, decision, duration_ms, status
                FROM gateway_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": request_id},
        ).fetchone()
        events = conn.execute(
            text(
                """
                SELECT agent_name, event_type
                FROM agent_events
                WHERE request_id = :request_id AND tenant_id = :tenant_id
                ORDER BY sequence ASC
                """
            ),
            {"request_id": request_id, "tenant_id": tenant_id},
        ).fetchall()

    assert gateway_row is not None
    assert gateway_row.request_id == request_id
    assert gateway_row.tenant_id == str(tenant_id)
    assert gateway_row.provider
    assert gateway_row.model
    assert gateway_row.decision == "ALLOW"
    assert gateway_row.duration_ms is not None
    assert gateway_row.status == "allowed"

    event_pairs = {(row.agent_name, row.event_type) for row in events}
    assert ("Gateway Agent", "API_KEY_VALIDATED") in event_pairs
    assert ("Policy Agent", "POLICY_EVALUATED") in event_pairs
    assert ("Decision Engine", "DECISION_EVALUATED") in event_pairs
    assert ("Provider Router", "PROVIDER_ROUTE_SELECTED") in event_pairs
    assert ("Audit Agent", "AUDIT_RECORD_STORED") in event_pairs
    assert ("Registrar Agent", "GATEWAY_REQUEST_RECORDED") in event_pairs


def test_gateway_lifecycle_records_approval_requirement_without_provider_call():
    session_id = f"gateway-approval-{uuid.uuid4().hex}"

    response = client.post(
        "/gateway/chat",
        headers=headers,
        json={"session_id": session_id, "message": "delete production database"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approval_required"

    with engine.connect() as conn:
        gateway_row = conn.execute(
            text(
                """
                SELECT decision, status
                FROM gateway_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": payload["request_id"]},
        ).fetchone()
        provider_events = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM agent_events
                WHERE request_id = :request_id AND agent_name = 'Provider Router'
                """
            ),
            {"request_id": payload["request_id"]},
        ).scalar()

    assert gateway_row.decision == "REQUIRE_APPROVAL"
    assert gateway_row.status == "pending_approval"
    assert provider_events == 0


def test_execute_approval_uses_gateway_service_and_records_lifecycle(monkeypatch):
    tenant_id = _tenant_id_for_test_key()
    approval = create_approval(
        query="delete production database",
        risk_level="HIGH",
        session_id=f"approval-execute-{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        request_id=f"req-original-{uuid.uuid4().hex}",
    )
    approval["status"] = "approved"
    approval["approved_at"] = datetime.now(timezone.utc).isoformat()
    approval["approved_by"] = conftest.tenant_email
    approval["approval_mfa_counter"] = int(time.time()) // 30
    approval["approval_mfa_verified"] = True
    approval["execution_expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    calls = []
    original_execute_approval = GatewayService.execute_approval

    def spy_execute_approval(self, *args, **kwargs):
        calls.append(kwargs["approval_record"]["approval_id"])
        return original_execute_approval(self, *args, **kwargs)

    monkeypatch.setattr(GatewayService, "execute_approval", spy_execute_approval)

    response = client.post(
        f"/execute/{approval['approval_id']}",
        headers=headers,
        json={"mfa_code": _mfa_code(1), "comment": "Execute lifecycle test."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"] == "Executed Successfully"
    assert payload["request_id"].startswith("req-")
    assert calls == [approval["approval_id"]]

    with engine.connect() as conn:
        gateway_row = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, provider, model, decision, duration_ms, status
                FROM gateway_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": payload["request_id"]},
        ).fetchone()
        events = conn.execute(
            text(
                """
                SELECT agent_name, event_type
                FROM agent_events
                WHERE request_id = :request_id AND tenant_id = :tenant_id
                ORDER BY sequence ASC
                """
            ),
            {"request_id": payload["request_id"], "tenant_id": tenant_id},
        ).fetchall()
        audit_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE approval_id = :approval_id AND execution_status = 'executed'
                """
            ),
            {"approval_id": approval["approval_id"]},
        ).scalar()

    assert gateway_row is not None
    assert gateway_row.request_id == payload["request_id"]
    assert gateway_row.tenant_id == str(tenant_id)
    assert gateway_row.provider
    assert gateway_row.model
    assert gateway_row.decision == "ALLOW"
    assert gateway_row.duration_ms is not None
    assert gateway_row.status == "allowed"

    event_pairs = {(row.agent_name, row.event_type) for row in events}
    assert ("Approval Execute", "APPROVAL_EXECUTION_STARTED") in event_pairs
    assert ("Decision Engine", "DECISION_EVALUATED") in event_pairs
    assert ("Provider Router", "PROVIDER_ROUTE_SELECTED") in event_pairs
    assert ("LLM Provider", "ROUTE_SELECTED") in event_pairs
    assert any(row.agent_name == "Security Agent" for row in events)
    assert ("Registrar Agent", "GATEWAY_REQUEST_RECORDED") in event_pairs
    assert audit_count >= 1
    assert get_approval(approval["approval_id"])["status"] == "executed"
