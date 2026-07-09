import time
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

import conftest
from approval_store import get_approval
from database import engine
from main import app, create_jwt, get_hotp_token


client = TestClient(app)


def _headers(tenant_id=None, email=None):
    token = create_jwt(
        {
            "sub": email or conftest.tenant_email,
            "email": email or conftest.tenant_email,
            "tenant_id": tenant_id or conftest.tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _mfa_code(offset=0):
    return get_hotp_token(conftest.totp_secret, int(time.time()) // 30 + offset)


def _create_other_tenant():
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO tenants (name, status, email_verified, domain_verified, totp_secret)
                VALUES (:name, 'active', TRUE, TRUE, :totp)
                RETURNING id
                """
            ),
            {"name": f"phase5-other-{uuid.uuid4().hex}", "totp": conftest.totp_secret},
        ).fetchone()
        conn.commit()
    return row[0]


def test_phase5_connector_scan_plan_and_hitl_gated_execution():
    headers = _headers()
    connector_payload = {
        "provider": "aws",
        "name": f"AWS Phase5 {uuid.uuid4().hex[:8]}",
        "credential_ref": "aws-test-credential-ref",
        "role_identifier": "arn:aws:iam::123456789012:role/AuthClawReadOnly",
        "region": "us-east-1",
        "scope": "read-only remediation",
    }

    created = client.post("/remediation/connectors", headers=headers, json=connector_payload)
    assert created.status_code == 200
    connector = created.json()
    assert connector["tenant_id"] == conftest.tenant_id
    assert connector["provider"] == "aws"

    tested = client.post(f"/remediation/connectors/{connector['id']}/test", headers=headers)
    assert tested.status_code == 200
    assert tested.json()["connector"]["status"] == "connected"
    assert tested.json()["lease"]["lease_id"].startswith("lease-")

    scan = client.post("/remediation/scans", headers=headers, json={"connector_id": connector["id"]})
    assert scan.status_code == 200
    scan_payload = scan.json()
    assert scan_payload["worker_id"].startswith("worker-")
    assert len(scan_payload["findings"]) >= 3
    finding = scan_payload["findings"][0]
    assert finding["approval_status"] == "not_requested"

    plan_response = client.post(f"/remediation/findings/{finding['id']}/plan", headers=headers)
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["status"] == "planned"
    assert plan["approval_id"] is None

    approval_response = client.post(f"/remediation/plans/{plan['id']}/approval", headers=headers)
    assert approval_response.status_code == 200
    approval_id = approval_response.json()["approval_id"]
    approval = get_approval(approval_id)
    assert approval["metadata"]["execution_target"] == "remediation"
    assert approval["metadata"]["remediation_plan_id"] == plan["id"]

    blocked_execute = client.post(
        f"/execute/{approval_id}",
        headers=headers,
        json={"mfa_code": _mfa_code(1), "comment": "Should not execute before approval."},
    )
    assert blocked_execute.status_code == 400

    approved = client.post(
        f"/approve/{approval_id}",
        headers=headers,
        json={"mfa_code": _mfa_code(), "comment": "Approve remediation."},
    )
    assert approved.status_code == 200

    stale_execute = client.post(
        f"/execute/{approval_id}",
        headers=headers,
        json={"mfa_code": _mfa_code(), "comment": "Stale execution MFA."},
    )
    assert stale_execute.status_code == 401

    executed = client.post(
        f"/execute/{approval_id}",
        headers=headers,
        json={"mfa_code": _mfa_code(1), "comment": "Execute remediation."},
    )
    assert executed.status_code == 200
    execution_payload = executed.json()
    assert execution_payload["provider"] == "aws"
    assert execution_payload["model"] == "remediation-worker"
    assert "remediation action" in execution_payload["response"].lower()

    worker = client.get(f"/remediation/workers/{execution_payload['request_id']}", headers=headers)
    assert worker.status_code == 200
    worker_payload = worker.json()
    assert worker_payload["status"] == "completed"
    assert worker_payload["approval_id"] == approval_id
    assert worker_payload["audit_events"]

    with engine.connect() as conn:
        revoked_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM worker_credential_leases
                WHERE tenant_id = :tenant_id AND connector_id = :connector_id AND revoked_at IS NOT NULL
                """
            ),
            {"tenant_id": conftest.tenant_id, "connector_id": connector["id"]},
        ).scalar()
    assert revoked_count >= 1


def test_phase5_worker_and_connector_isolation_between_tenants():
    headers = _headers()
    other_tenant = _create_other_tenant()
    other_headers = _headers(other_tenant, "phase5-other@example.com")

    created = client.post(
        "/remediation/connectors",
        headers=headers,
        json={
            "provider": "github",
            "name": f"GitHub Phase5 {uuid.uuid4().hex[:8]}",
            "credential_ref": "123456",
            "role_identifier": "app-123",
            "region": "org:authclaw",
            "scope": "repos read",
        },
    )
    assert created.status_code == 200
    connector_id = created.json()["id"]

    scan = client.post("/remediation/scans", headers=headers, json={"connector_id": connector_id})
    assert scan.status_code == 200
    worker_id = scan.json()["worker_id"]

    other_list = client.get("/remediation/connectors", headers=other_headers)
    assert other_list.status_code == 200
    assert all(item["id"] != connector_id for item in other_list.json())

    other_worker = client.get(f"/remediation/workers/{worker_id}", headers=other_headers)
    assert other_worker.status_code == 404
