import uuid
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from approval_store import create_approval, get_approval, get_approval_history
from database import engine
from database.migrations import run_startup_migrations
from main import app, create_jwt, get_hotp_token


client = TestClient(app)
_schema_ready = False
TEST_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


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
                INSERT INTO tenants (name, status, email_verified, domain_verified, totp_secret)
                VALUES (:name, 'active', TRUE, TRUE, :totp_secret)
                RETURNING id
                """
            ),
            {"name": name, "totp_secret": TEST_TOTP_SECRET},
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


def _mfa_code(offset: int = 0) -> str:
    return get_hotp_token(TEST_TOTP_SECRET, int(time.time()) // 30 + offset)


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

    missing_mfa = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        json={"comment": "Reviewed incident ticket and approved for remediation."},
    )

    assert missing_mfa.status_code == 401

    empty_body = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        data="",
    )

    assert empty_body.status_code == 401

    response = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        json={"mfa_code": _mfa_code(), "comment": "Reviewed incident ticket and approved for remediation."},
    )

    assert response.status_code == 200
    reloaded = get_approval(approval["approval_id"])
    assert reloaded["status"] == "approved"
    assert reloaded["approved_by"] == "phase8-approver@example.com"
    assert reloaded["mfa_verified"] is True
    assert reloaded["approval_mfa_verified"] is True
    assert reloaded["approval_mfa_binding_hash"]
    assert reloaded["execution_expires_at"]

    history = get_approval_history(approval["approval_id"], tenant_id=tenant_id)
    actions = [event["action"] for event in history]
    assert "created" in actions
    assert "approval_mfa_failed" in actions
    assert "approved" in actions
    approved_event = next(event for event in history if event["action"] == "approved")
    assert approved_event["actor"] == "phase8-approver@example.com"
    assert approved_event["mfa_verified"] is True

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


def test_phase4_execution_requires_fresh_mfa_and_rejects_replay_and_transfer():
    tenant_id = _create_test_tenant(f"Phase4 Execute Tenant {uuid.uuid4().hex}")
    approver_headers = _auth_headers(tenant_id, "phase4-approver@example.com")
    other_headers = _auth_headers(tenant_id, "phase4-other@example.com")
    approval = create_approval(
        query="Summarize compliance posture.",
        risk_level="HIGH",
        tenant_id=tenant_id,
        request_id=f"req-phase4-exec-{uuid.uuid4().hex}",
        reason="high_risk",
    )

    approved = client.post(
        f"/approve/{approval['approval_id']}",
        headers=approver_headers,
        json={"mfa_code": _mfa_code(), "comment": "Approved for execution."},
    )
    assert approved.status_code == 200

    missing_mfa = client.post(
        f"/execute/{approval['approval_id']}",
        headers=approver_headers,
        json={"comment": "Execute now."},
    )
    assert missing_mfa.status_code == 401

    stale_mfa = client.post(
        f"/execute/{approval['approval_id']}",
        headers=approver_headers,
        json={"mfa_code": _mfa_code(), "comment": "Execute with stale code."},
    )
    assert stale_mfa.status_code == 401

    transfer = client.post(
        f"/execute/{approval['approval_id']}",
        headers=other_headers,
        json={"mfa_code": _mfa_code(1), "comment": "Different user tries execution."},
    )
    assert transfer.status_code == 403

    executed = client.post(
        f"/execute/{approval['approval_id']}",
        headers=approver_headers,
        json={"mfa_code": _mfa_code(1), "comment": "Execute with fresh code."},
    )
    assert executed.status_code == 200

    reloaded = get_approval(approval["approval_id"])
    assert reloaded["status"] == "executed"
    assert reloaded["execution_mfa_verified"] is True
    assert reloaded["execution_mfa_binding_hash"]
    assert reloaded["execution_token_hash"]
    assert reloaded["execution_token_used_at"]

    replay = client.post(
        f"/execute/{approval['approval_id']}",
        headers=approver_headers,
        json={"mfa_code": _mfa_code(1), "comment": "Replay."},
    )
    assert replay.status_code == 400

    history = get_approval_history(approval["approval_id"], tenant_id=tenant_id)
    actions = [event["action"] for event in history]
    for expected in ["approved", "execution_mfa_failed", "transfer_rejected", "executing", "executed", "replay_rejected"]:
        assert expected in actions


def test_phase4_execution_window_expiry_blocks_execution():
    tenant_id = _create_test_tenant(f"Phase4 Expiry Tenant {uuid.uuid4().hex}")
    headers = _auth_headers(tenant_id, "phase4-expiry@example.com")
    approval = create_approval(
        query="Summarize compliance posture.",
        risk_level="HIGH",
        tenant_id=tenant_id,
        request_id=f"req-phase4-expiry-{uuid.uuid4().hex}",
        reason="high_risk",
    )
    approved = client.post(
        f"/approve/{approval['approval_id']}",
        headers=headers,
        json={"mfa_code": _mfa_code(), "comment": "Approved."},
    )
    assert approved.status_code == 200

    reloaded = get_approval(approval["approval_id"])
    reloaded["execution_expires_at"] = "2000-01-01T00:00:00+00:00"

    blocked = client.post(
        f"/execute/{approval['approval_id']}",
        headers=headers,
        json={"mfa_code": _mfa_code(1), "comment": "Too late."},
    )
    assert blocked.status_code == 400
    assert get_approval(approval["approval_id"])["status"] == "expired"
