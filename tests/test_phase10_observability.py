import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from database.migrations import run_startup_migrations
from main import app, create_jwt
from verify_audit import create_audit_block


client = TestClient(app)
_schema_ready = False


def _ensure_schema():
    global _schema_ready
    if not _schema_ready:
        run_startup_migrations()
        _schema_ready = True


def _create_tenant() -> int:
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
            {"name": f"Phase10 Tenant {uuid.uuid4().hex}"},
        ).fetchone()
        conn.commit()
    return row[0]


def _headers(tenant_id: int) -> dict:
    token = create_jwt(
        {
            "sub": "phase10-admin@example.com",
            "email": "phase10-admin@example.com",
            "tenant_id": tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_observability_data(tenant_id: int) -> None:
    tenant_text = str(tenant_id)
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO gateway_requests (
                    timestamp, created_at, risk_level, allowed, status, request_id,
                    tenant_id, route_id, provider, model, latency, tokens_in,
                    tokens_out, decision, duration_ms
                )
                VALUES
                    (NOW(), NOW(), 'LOW', TRUE, 'allowed', :allowed_request,
                     :tenant_text, 'route-a', 'openai', 'gpt-4o', 120, 10, 20, 'ALLOW', 120),
                    (NOW(), NOW(), 'HIGH', FALSE, 'blocked', :blocked_request,
                     :tenant_text, 'route-b', 'gemini', 'gemini-2.5-flash-lite', 90, 8, 0, 'BLOCK', 90)
                """
            ),
            {
                "tenant_text": tenant_text,
                "allowed_request": f"req-{uuid.uuid4()}",
                "blocked_request": f"req-{uuid.uuid4()}",
            },
        )
        doc = conn.execute(
            text(
                """
                INSERT INTO documents (tenant_id, filename, source, size_bytes, status, risk_score, severity)
                VALUES (:tenant_id, 'phase10.pdf', 'test', 1024, 'completed', 80, 'HIGH')
                RETURNING id
                """
            ),
            {"tenant_id": tenant_id},
        ).fetchone()
        conn.execute(
            text(
                """
                INSERT INTO document_findings (
                    tenant_id, document_id, finding_type, matched_pattern,
                    matched_text, risk_level, recommendation
                )
                VALUES
                    (:tenant_id, :document_id, 'PII', 'email', 'hidden@example.com', 'HIGH', 'Redact'),
                    (:tenant_id, :document_id, 'Secret', 'api_key', 'sk-hidden', 'HIGH', 'Rotate')
                """
            ),
            {"tenant_id": tenant_id, "document_id": doc[0]},
        )
        conn.execute(
            text(
                """
                INSERT INTO agent_events (
                    tenant_id, session_id, request_id, sequence,
                    agent_name, event_type, details
                )
                VALUES (
                    :tenant_id, 'phase10-session', :request_id, 1,
                    'Security Agent', 'OUTPUT_PII_REDACTED', 'Output redaction applied.'
                )
                """
            ),
            {"tenant_id": tenant_id, "request_id": f"req-{uuid.uuid4()}"},
        )
        conn.execute(
            text(
                """
                INSERT INTO gateway_approvals (
                    approval_id, request_id, tenant_id, status,
                    requested_action, query, risk_level
                )
                VALUES
                    (:pending_id, :pending_request, :tenant_id, 'pending', 'Review', 'Needs review', 'HIGH'),
                    (:approved_id, :approved_request, :tenant_id, 'approved', 'Approve', 'Approved review', 'MEDIUM')
                """
            ),
            {
                "tenant_id": tenant_id,
                "pending_id": f"approval-{uuid.uuid4()}",
                "pending_request": f"req-{uuid.uuid4()}",
                "approved_id": f"approval-{uuid.uuid4()}",
                "approved_request": f"req-{uuid.uuid4()}",
            },
        )
        conn.commit()

    create_audit_block(
        query="Phase 10 audit verification record",
        response="Audit analytics seed",
        allowed=True,
        risk_level="LOW",
        approval_status="completed",
        tenant_id=tenant_id,
    )


def test_governance_analytics_aggregates_tenant_runtime_data():
    tenant_id = _create_tenant()
    _seed_observability_data(tenant_id)

    response = client.get("/analytics/governance", headers=_headers(tenant_id))

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == tenant_id
    assert body["gateway"]["total_requests"] == 2
    assert body["gateway"]["allowed_requests"] == 1
    assert body["gateway"]["blocked_requests"] == 1
    assert body["gateway"]["tokens_total"] == 38
    assert body["providers"][0]["requests"] >= 1
    assert body["blocked_requests"]["by_risk_level"]["HIGH"] == 1
    assert body["redactions"]["document_findings"] == 2
    assert body["redactions"]["agent_redaction_events"] == 1
    assert body["redactions"]["by_type"]["PII"] == 1
    assert body["redactions"]["by_type"]["Secret"] == 1
    assert body["approvals"]["pending"] == 1
    assert body["approvals"]["approved"] == 1
    assert body["audit"]["valid"] is True
    assert body["audit"]["records_checked"] >= 1
    assert body["audit"]["latest_hash"]
    assert body["audit"]["export_endpoints"]["csv"] == "/audit/export/csv"


def test_audit_exports_remain_available_for_phase10_reports():
    tenant_id = _create_tenant()
    _seed_observability_data(tenant_id)
    headers = _headers(tenant_id)

    csv_response = client.get("/audit/export/csv", headers=headers)
    pdf_response = client.get("/audit/export/pdf", headers=headers)

    assert csv_response.status_code == 200
    assert "Record ID" in csv_response.text
    assert "Phase 10 audit verification record" in csv_response.text
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
