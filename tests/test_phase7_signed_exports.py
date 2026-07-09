import copy
import uuid

from fastapi.testclient import TestClient

import conftest
from main import app, create_jwt
from verify_audit import create_audit_block


client = TestClient(app)


def _headers():
    token = create_jwt(
        {
            "sub": conftest.tenant_email,
            "email": conftest.tenant_email,
            "tenant_id": conftest.tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _seed_audit_and_evidence(headers):
    create_audit_block(
        query="Phase 7 export verification request",
        response="Allowed for signed export test",
        allowed=True,
        risk_level="LOW",
        approval_status="N/A",
        tenant_id=conftest.tenant_id,
    )
    response = client.post(
        "/evidence/collect",
        headers=headers,
        json={
            "name": f"Phase 7 SOC2 Evidence {uuid.uuid4().hex[:8]}",
            "category": "SOC2",
            "file_path": "/evidence/phase7-soc2.pdf",
        },
    )
    assert response.status_code == 200


def test_phase7_signed_audit_export_verifies_and_tamper_fails():
    headers = _headers()
    _seed_audit_and_evidence(headers)

    package_response = client.get("/audit/export/package", headers=headers, params={"framework": "SOC2"})
    assert package_response.status_code == 200
    package = package_response.json()
    manifest = package["manifest"]

    assert manifest["version"] == "authclaw.signed-export.v1"
    assert manifest["framework_scope"] == "SOC2"
    assert manifest["hash_chain_root"]
    assert manifest["signing_key_id"].startswith("authclaw-export-")
    assert manifest["public_key_pem"].startswith("-----BEGIN PUBLIC KEY-----")

    verified = client.post(
        "/audit/export/verify",
        json={"payload_b64": package["payload_b64"], "manifest": manifest},
    )
    assert verified.status_code == 200
    assert verified.json()["valid"] is True

    tampered_payload = copy.deepcopy(package["payload"])
    tampered_payload["tenant_id"] = 999999
    tampered = client.post(
        "/audit/export/verify",
        json={"payload": tampered_payload, "manifest": manifest},
    )
    assert tampered.status_code == 200
    assert tampered.json()["valid"] is False
    assert "payload hash mismatch" in tampered.json()["reason"]


def test_phase7_auditor_package_and_public_trust_state_are_signed():
    headers = _headers()
    _seed_audit_and_evidence(headers)

    auditor_response = client.get("/auditor/package/export", headers=headers, params={"framework": "SOC2"})
    assert auditor_response.status_code == 200
    auditor_package = auditor_response.json()
    assert auditor_package["manifest"]["export_type"] == "auditor-package"
    assert auditor_package["payload"]["framework_scores"]["soc2"] >= 0
    assert auditor_package["payload"]["control_evidence"]
    assert auditor_package["payload"]["audit_chain"]["valid"] is True

    auditor_verify = client.post(
        "/audit/export/verify",
        json={
            "payload_b64": auditor_package["payload_b64"],
            "manifest": auditor_package["manifest"],
        },
    )
    assert auditor_verify.status_code == 200
    assert auditor_verify.json()["valid"] is True

    trust_response = client.get("/trust/public")
    assert trust_response.status_code == 200
    trust_state = trust_response.json()
    assert trust_state["status"] == "published"
    assert trust_state["verification"]["valid"] is True
    assert trust_state["manifest"]["export_type"] == "trust-center-state"
    assert trust_state["payload"]["framework_scores"]["corpus_version"]
