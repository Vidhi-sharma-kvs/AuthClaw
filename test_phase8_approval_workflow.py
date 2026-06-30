import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from approval_store import create_approval, get_approval, get_approval_history
from database import engine
from database.migrations import run_startup_migrations
from main import app, create_jwt


client = TestClient(app)
_schema_ready = False


def _ensure_schema():
    global _schema_ready
    if not _schema_ready:
        run_startup_migrations()
        _schema_ready = True


def _create_test_tenant(name: str) -> int:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO tenants (name, status, email_verified, domain_verified)
                VALUES (:name, 'active', TRUE, TRUE)
                RETURNING id
                """
            ),
            {"name": name},
        ).fetchone()
        conn.commit()
    return row[0]


def _auth_headers(tenant_id: int, email: str) -> dict:
    token = create_jwt(
        {
            "sub": email,
            "email": email,
            "tenant_id": tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_phase8_approval_queue_is_tenant_scoped_and_reasoned():
    tenant_a = _create_test_tenant(f"Phase8 Tenant A {uuid.uuid4().hex}")
    tenant_b = _create_test_tenant(f"Phase8 Tenant B {uuid.uuid4().hex}")

    approval_a = create_approval(
        query="Send customer PII to unknown provider",
        risk_level="HIGH",
        tenant_id=tenant_a,
        request_id=f"req-phase8-a-{uuid.uuid4().hex}",
        reason="sensitive_data",
        metadata={"policy_decision": "REQUIRE_APPROVAL"},
    )
    approval_b = create_approval(
        query="Bypass policy controls",
        risk_level="HIGH",
        tenant_id=tenant_b,
        request_id=f"req-phase8-b-{uuid.uuid4().hex}",
        reason="policy_violation",
    )

    headers_a = _auth_headers(tenant_a, "phase8-admin-a@example.com")
    response = client.get("/gateway/approvals", headers=headers_a)

    assert response.status_code == 200
    payload = response.json()
    ids = {item["approval_id"] for item in payload}
    assert approval_a["approval_id"] in ids
    assert approval_b["approval_id"] not in ids

    selected = next(item for item in payload if item["approval_id"] == approval_a["approval_id"])
    assert selected["reason"] == "sensitive_data"
    assert selected["tenant_id"] == tenant_a
    assert selected["history"]

    cross_tenant = client.get(f"/approvals/{approval_b['approval_id']}", headers=headers_a)
    assert cross_tenant.status_code == 404


def test_phase8_approval_comments_actor_and_history_are_persisted():
    tenant_id = _create_test_tenant(f"Phase8 Comment Tenant {uuid.uuid4().hex}")
    headers = _auth_headers(tenant_id, "phase8-approver@example.com")
    approval = create_approval(
        query="Run high-risk production operation",
        risk_level="HIGH",
        tenant_id=tenant_id,
        request_id=f"req-phase8-comment-{uuid.uuid4().hex}",
        reason="high_risk",
    )

    response = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        json={"comment": "Reviewed incident ticket and approved for remediation."},
    )

    assert response.status_code == 401

    response = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        data="",
    )

    assert response.status_code == 200
    reloaded = get_approval(approval["approval_id"])
    assert reloaded["status"] == "approved"
    assert reloaded["approved_by"] == "phase8-approver@example.com"
    assert reloaded["mfa_verified"] is False

    history = get_approval_history(approval["approval_id"], tenant_id=tenant_id)
    actions = [event["action"] for event in history]
    assert "created" in actions
    assert "approved" in actions
    approved_event = next(event for event in history if event["action"] == "approved")
    assert approved_event["actor"] == "phase8-approver@example.com"
    assert approved_event["mfa_verified"] is False

    rejected = create_approval(
        query="Request contains unknown provider risk",
        risk_level="HIGH",
        tenant_id=tenant_id,
        request_id=f"req-phase8-reject-{uuid.uuid4().hex}",
        reason="unknown_provider_risk",
    )
    reject_response = client.post(
        f"/reject/{rejected['approval_id']}",
        headers=headers,
        json={"comment": "Provider route is not approved for this tenant."},
    )

    assert reject_response.status_code == 200
    rejected_history = get_approval_history(rejected["approval_id"], tenant_id=tenant_id)
    reject_event = next(event for event in rejected_history if event["action"] == "rejected")
    assert reject_event["comment"] == "Provider route is not approved for this tenant."
