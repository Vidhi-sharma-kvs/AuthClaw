import os
import json
import pytest
from sqlalchemy import text
from database import engine

from document_processing.connectors import scan_s3_bucket_security, is_real_connectors_enabled
from document_processing.drift import get_current_framework_scores, record_compliance_snapshot
from document_processing.reports import (
    generate_executive_summary_report,
    generate_technical_findings_report,
    generate_auditor_evidence_report
)
from document_processing.alerts import trigger_security_alert, ALERTS_LOG

@pytest.fixture
def clean_database():
    """Ensure clean compliance and document tables."""
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM compliance_drift_alerts"))
        conn.execute(text("DELETE FROM compliance_score_history"))
        conn.execute(text("DELETE FROM document_findings"))
        conn.execute(text("DELETE FROM documents"))
        conn.commit()
    yield

def test_s3_configuration_checks():
    """Verify that S3 configuration scanner runs and identifies misconfigurations."""
    # Under simulated/mock connectors (the default test sandbox), it must return mock findings
    findings = scan_s3_bucket_security("company-compliance-docs")
    assert len(findings) > 0
    
    types = [f["finding_type"] for f in findings]
    severities = [f["risk_level"] for f in findings]
    
    assert "S3_ENCRYPTION_DISABLED" in [f["matched_pattern"] for f in findings]
    assert "CRITICAL" in severities or "HIGH" in severities
    assert "SOC2" in findings[0]["recommendation"]

def test_compliance_score_and_drift_tracking(clean_database):
    """Verify compliance drift is tracked in history and triggers alerts on score drop."""
    # 1. Insert documents and findings
    with engine.connect() as conn:
        res = conn.execute(
            text("INSERT INTO documents (filename, source, size_bytes, status) VALUES ('test1.pdf', 's3', 1000, 'completed') RETURNING id")
        )
        doc_id = res.fetchone()[0]
        
        # Save a high severity finding that drops SOC2 and HIPAA scores
        conn.execute(
            text("""
            INSERT INTO document_findings (document_id, finding_type, matched_pattern, matched_text, risk_level, recommendation, impact, priority, location_evidence)
            VALUES (:doc_id, 'Regulatory', 'SOC2_MFA_MISSING', 'No MFA', 'HIGH', 'Enable MFA', 'Account hijack risk', 'P1', 'Line 1')
            """),
            {"doc_id": doc_id}
        )
        conn.commit()

    # Calculate live scores
    scores = get_current_framework_scores()
    assert scores["SOC2"] < 100
    assert scores["GDPR"] == 100 # No GDPR gap loaded
    
    # 2. Record initial compliance snapshot
    record_compliance_snapshot()
    
    # Verify score history is written
    with engine.connect() as conn:
        history_cnt = conn.execute(text("SELECT COUNT(*) FROM compliance_score_history")).scalar()
        assert history_cnt > 0
        
    # 3. Simulate score drop by adding another critical finding
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO document_findings (document_id, finding_type, matched_pattern, matched_text, risk_level, recommendation, impact, priority, location_evidence)
            VALUES (:doc_id, 'Regulatory', 'SOC2_RBAC_MISSING', 'No RBAC', 'HIGH', 'Enable RBAC', 'Privilege leak', 'P1', 'Line 10')
            """),
            {"doc_id": doc_id}
        )
        conn.commit()
        
    # Record another snapshot to trigger drift alert (drop of > 5 points)
    record_compliance_snapshot()
    
    with engine.connect() as conn:
        alerts_cnt = conn.execute(text("SELECT COUNT(*) FROM compliance_drift_alerts")).scalar()
        assert alerts_cnt > 0
        
        alert = conn.execute(text("SELECT framework, score_drop, previous_score, current_score FROM compliance_drift_alerts LIMIT 1")).fetchone()
        assert alert[0] == "SOC2"
        assert alert[1] > 5

def test_report_downloads(clean_database):
    """Verify PDF/CSV/JSON downloadable report package outputs."""
    # Seed data
    with engine.connect() as conn:
        res = conn.execute(
            text("INSERT INTO documents (filename, source, size_bytes, status) VALUES ('test_report.pdf', 's3', 5000, 'completed') RETURNING id")
        )
        doc_id = res.fetchone()[0]
        conn.execute(
            text("""
            INSERT INTO document_findings (document_id, finding_type, matched_pattern, matched_text, risk_level, recommendation, impact, priority, location_evidence)
            VALUES (:doc_id, 'Secret', 'AWS_ACCESS_KEY', 'AKIA...', 'CRITICAL', 'Rotate key', 'Exposed cloud credential', 'P1', 'Line 5')
            """),
            {"doc_id": doc_id}
        )
        conn.commit()
        
    # Generate reports
    exec_pdf = generate_executive_summary_report("pdf")
    exec_csv = generate_executive_summary_report("csv")
    exec_json = generate_executive_summary_report("json")
    
    assert isinstance(exec_pdf, bytes)
    assert len(exec_pdf) > 0
    assert exec_pdf.startswith(b"%PDF")
    
    assert isinstance(exec_csv, bytes)
    assert b"Executive Compliance Summary" in exec_csv
    
    assert isinstance(exec_json, bytes)
    exec_data = json.loads(exec_json.decode("utf-8"))
    assert exec_data["compliance_score"] is not None
    
    # Technical findings
    tech_pdf = generate_technical_findings_report("pdf")
    tech_csv = generate_technical_findings_report("csv")
    tech_json = generate_technical_findings_report("json")
    
    assert isinstance(tech_pdf, bytes)
    assert tech_pdf.startswith(b"%PDF")
    assert b"AWS_ACCESS_KEY" in tech_csv
    assert "test_report.pdf" in tech_json.decode("utf-8")
    
    # Auditor evidence
    audit_pdf = generate_auditor_evidence_report("pdf")
    audit_csv = generate_auditor_evidence_report("csv")
    audit_json = generate_auditor_evidence_report("json")
    
    assert isinstance(audit_pdf, bytes)
    assert audit_pdf.startswith(b"%PDF")
    assert b"Verification" in audit_csv
    assert "chain_verification" in audit_json.decode("utf-8")

def test_real_time_alerting_fallback():
    """Verify security alerts are written to local alerts.log fallback file when SMTP is inactive."""
    if os.path.exists(ALERTS_LOG):
        os.remove(ALERTS_LOG)
        
    finding = {
        "finding_type": "Secret",
        "risk_level": "CRITICAL",
        "matched_pattern": "AWS_ACCESS_KEY",
        "matched_text": "AKIAIOSFODNN7EXAMPLE",
        "recommendation": "Rotate keys immediately.",
        "impact": "Full AWS administrative take-over.",
        "priority": "P1",
        "location_evidence": "Line 42"
    }
    
    # Trigger alert
    trigger_security_alert(finding, "credentials.txt")
    
    # Check that alerts log has been written
    assert os.path.exists(ALERTS_LOG)
    with open(ALERTS_LOG, "r", encoding="utf-8") as f:
        log_content = f.read()
        assert "[AuthClaw Alert] CRITICAL Security Leak Detected" in log_content
        assert "Full AWS administrative take-over." in log_content
        assert "credentials.txt" in log_content
