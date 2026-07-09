import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

import conftest
from database import engine
from main import app, create_jwt
from services.compliance_evidence_engine import ComplianceEvidenceEngine


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


def _insert_document_finding(risk_level="HIGH"):
    with engine.connect() as conn:
        document_id = conn.execute(
            text(
                """
                INSERT INTO documents (
                    tenant_id, filename, source, status, size_bytes, risk_score,
                    severity, created_at, updated_at
                )
                VALUES (
                    :tenant_id, :filename, 'phase6-test', 'active', 128, 90,
                    :risk_level, NOW(), NOW()
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": conftest.tenant_id,
                "filename": f"phase6-{uuid.uuid4().hex}.txt",
                "risk_level": risk_level,
            },
        ).fetchone()[0]
        finding_id = conn.execute(
            text(
                """
                INSERT INTO document_findings (
                    tenant_id, document_id, finding_type, matched_pattern,
                    matched_text, risk_level, recommendation, impact, priority,
                    location_evidence
                )
                VALUES (
                    :tenant_id, :document_id, 'PII', 'GDPR personal data exposure',
                    'patient email leaked', :risk_level, 'Redact and restrict access',
                    'GDPR personal data and HIPAA PHI exposure', 'P1', 'Line 1'
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": conftest.tenant_id,
                "document_id": document_id,
                "risk_level": risk_level,
            },
        ).fetchone()[0]
        conn.commit()
    return finding_id


def test_phase6_control_scores_are_evidence_backed_and_exportable():
    headers = _headers()
    evidence_name = f"SOC2 MFA Evidence {uuid.uuid4().hex[:8]}"

    collect = client.post(
        "/evidence/collect",
        headers=headers,
        json={
            "name": evidence_name,
            "category": "SOC2",
            "file_path": f"/evidence/{evidence_name}.pdf",
        },
    )
    assert collect.status_code == 200

    _insert_document_finding("HIGH")

    controls = client.get("/compliance/controls", headers=headers, params={"framework": "SOC2"})
    assert controls.status_code == 200
    assert any(item["control_id"] == "SOC2-CC6.1" for item in controls.json())

    scores = client.get("/compliance/framework-scores", headers=headers)
    assert scores.status_code == 200
    payload = scores.json()
    assert payload["corpus_version"] == ComplianceEvidenceEngine.corpus_version
    assert isinstance(payload["soc2"], int)
    assert isinstance(payload["gdpr"], int)
    assert isinstance(payload["hipaa"], int)

    soc2_controls = payload["soc2_controls"]["items"]
    assert soc2_controls
    assert all(item["reason"] for item in soc2_controls)
    assert all(item["source_event"] for item in soc2_controls)
    assert all(item["calculated_at"] for item in soc2_controls)
    assert any(item["evidence_count"] > 0 for item in soc2_controls)

    evidence = client.get("/compliance/controls/SOC2-CC6.1/evidence", headers=headers)
    assert evidence.status_code == 200
    evidence_rows = evidence.json()
    assert any(row["evidence_hash"].startswith("sha256-") for row in evidence_rows)

    exported = client.get(
        "/compliance/evidence/export/csv",
        headers=headers,
        params={"framework": "SOC2"},
    )
    assert exported.status_code == 200
    assert "framework,control_id,source_type" in exported.text
    assert "sha256-" in exported.text

    changes = client.get("/compliance/score-changes", headers=headers, params={"framework": "SOC2"})
    assert changes.status_code == 200
    assert changes.json()
    assert {"reason", "source_event", "created_at"}.issubset(changes.json()[0].keys())


def test_phase6_corpus_status_and_score_drift_detection():
    headers = _headers()

    baseline = client.get("/compliance/framework-scores", headers=headers)
    assert baseline.status_code == 200
    baseline_gdpr = baseline.json()["gdpr"]

    _insert_document_finding("CRITICAL")

    updated = client.get("/compliance/framework-scores", headers=headers)
    assert updated.status_code == 200
    assert updated.json()["gdpr"] <= baseline_gdpr

    changes = client.get("/compliance/score-changes", headers=headers, params={"framework": "GDPR"})
    assert changes.status_code == 200
    assert any(item["previous_score"] != item["current_score"] for item in changes.json())

    corpus = client.get("/compliance/corpus", headers=headers)
    assert corpus.status_code == 200
    corpus_payload = corpus.json()
    assert corpus_payload["version_id"] == ComplianceEvidenceEngine.corpus_version
    assert corpus_payload["production_vector_backend"]
    assert "indexed_chunks" in corpus_payload
