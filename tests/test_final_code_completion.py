from fastapi.testclient import TestClient

import conftest
from main import app, create_jwt
from services.policy_bundle_manager import PolicyBundleManager
from services.sensitive_data_detection import SensitiveDataDetector


client = TestClient(app)


def _headers(role="Super Admin"):
    token = create_jwt(
        {
            "sub": conftest.tenant_email,
            "email": conftest.tenant_email,
            "tenant_id": conftest.tenant_id,
            "role": role,
            "permissions": "all_access",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_presidio_can_be_disabled_without_breaking_custom_redaction(monkeypatch):
    monkeypatch.setenv("USE_PRESIDIO", "false")
    redacted, findings = SensitiveDataDetector(conftest.tenant_id).redact(
        "Email priya@example.com and PAN ABCDE1234F are sensitive.",
        username="tester",
    )

    assert "priya@example.com" not in redacted
    assert "ABCDE1234F" not in redacted
    assert {item["matched_pattern"] for item in findings} >= {"email", "pan"}


def test_policy_bundle_lifecycle_build_promote_and_rollback(tmp_path):
    manager = PolicyBundleManager(bundle_dir=str(tmp_path))
    first = manager.build_bundle(conftest.tenant_id, actor="tester")
    second = manager.build_bundle(conftest.tenant_id, actor="tester")

    active = manager.promote_bundle(conftest.tenant_id, second["bundle_id"], actor="tester")
    rolled_back = manager.rollback_bundle(conftest.tenant_id, actor="tester")
    listed = manager.list_bundles(conftest.tenant_id)

    assert first["sha256"]
    assert active["bundle_id"] == second["bundle_id"]
    assert rolled_back["bundle_id"] == first["bundle_id"]
    assert listed["active_bundle"]["bundle_id"] == first["bundle_id"]
    assert listed["yaml_fallback"] is True


def test_redteam_runtime_persists_history_and_report():
    run_response = client.post("/redteam/run", headers=_headers())
    assert run_response.status_code == 200
    assert run_response.json()["stored"] >= 1

    report = client.get("/redteam/report", headers=_headers())
    assert report.status_code == 200
    body = report.json()
    assert body["total_probes"] >= 1
    assert "by_severity" in body

    history = client.get("/redteam/history", headers=_headers())
    assert history.status_code == 200
    assert history.json()


def test_tenant_plan_api_exposes_real_limits_and_allows_admin_override():
    current = client.get("/tenant/plan", headers=_headers())
    assert current.status_code == 200
    assert current.json()["current_plan"] in {"free", "starter", "professional", "enterprise", "unlimited"}

    updated = client.post(
        "/tenant/plan/override",
        headers=_headers(),
        json={"plan": "starter", "override_reason": "test override"},
    )
    assert updated.status_code == 200
    assert updated.json()["current_plan"] == "starter"
    assert updated.json()["admin_override"]["reason"] == "test override"

    denied = client.post(
        "/tenant/plan/override",
        headers=_headers(role="Developer"),
        json={"plan": "enterprise", "override_reason": "not allowed"},
    )
    assert denied.status_code == 403


def test_framework_explorer_returns_requested_extended_frameworks():
    response = client.get("/compliance/framework-explorer?framework=ISO27001", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["controls"]
    assert all(item["framework"] == "ISO27001" for item in body["controls"])
    assert "framework_scores" in body
