from fastapi.testclient import TestClient

import conftest
from main import app, create_jwt
from services.production_readiness import disaster_recovery_readiness, production_readiness_report, terraform_coverage
from services.rbac_matrix import ALL_ROLES, coverage_report, role_allowed
from services.tenant_isolation_report import tenant_isolation_report


client = TestClient(app)


def _headers(role="Super Admin", tenant_id=None):
    token = create_jwt(
        {
            "sub": conftest.tenant_email,
            "email": conftest.tenant_email,
            "tenant_id": tenant_id or conftest.tenant_id,
            "role": role,
            "permissions": "all_access",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_rbac_matrix_covers_every_backend_route_and_roles():
    report = coverage_report(app)

    assert report["complete"] is True
    assert report["unmapped_endpoints"] == []
    assert set(report["roles"]) == set(ALL_ROLES)
    assert role_allowed("Super Admin", "GET", "/providers")
    assert not role_allowed("Auditor", "POST", "/providers/connect")
    assert role_allowed("Developer", "POST", "/gateway/chat")
    assert not role_allowed("Developer", "POST", "/approve/approval-id")


def test_security_readiness_endpoints_are_tenant_admin_protected():
    for path in [
        "/security/rbac/matrix",
        "/security/tenant-isolation",
        "/security/secrets/health",
        "/security/production-readiness",
    ]:
        response = client.get(path, headers=_headers())
        assert response.status_code == 200
        body = response.json()
        assert body["tenant_id"] == conftest.tenant_id

    denied = client.get("/security/rbac/matrix", headers=_headers(role="Developer"))
    assert denied.status_code == 403


def test_tenant_isolation_report_has_no_unclassified_table_gaps():
    report = tenant_isolation_report()

    assert report["complete"] is True
    assert report["gap_count"] == 0
    assert report["gaps"] == []
    assert all(item["protected"] for item in report["tables"])


def test_trust_center_runtime_health_and_public_state_are_signed():
    health = client.get("/trust/public/health")
    assert health.status_code == 200
    assert health.json()["trust_center"]["signature_valid"] is True

    state = client.get("/trust/public")
    assert state.status_code == 200
    body = state.json()
    assert body["status"] == "published"
    assert body["verification"]["valid"] is True
    assert "runtime" in body["payload"]
    assert body["payload"]["runtime"]["metrics"]["total_requests"] >= 0
    assert body["manifest"]["export_type"] == "trust-center-state"


def test_code_only_production_readiness_reports_are_complete_for_code():
    report = production_readiness_report(app)

    assert report["rbac"]["complete"] is True
    assert report["tenant_isolation"]["complete"] is True
    assert report["dr"]["complete_for_code"] is True
    assert report["terraform"]["complete"] is True
    assert "External penetration testing" in report["non_code_gaps"]


def test_terraform_and_dr_readiness_do_not_claim_live_evidence():
    terraform = terraform_coverage()
    dr = disaster_recovery_readiness()

    assert terraform["complete"] is True
    assert terraform["missing"] == []
    assert dr["complete_for_code"] is True
    assert dr["requires_live_dr_drill"] is True
