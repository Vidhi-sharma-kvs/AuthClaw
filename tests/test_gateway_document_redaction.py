import hashlib
import io
import base64

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import API_KEY, app


client = TestClient(app)
headers = {
    "X-API-Key": API_KEY,
    "Authorization": f"Bearer {API_KEY}",
}


def _tenant_id_for_test_key():
    key_hash = hashlib.sha256(API_KEY.encode("utf-8")).hexdigest()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM tenant_api_keys WHERE key_hash = :hash"),
            {"hash": key_hash},
        ).scalar()


def test_gateway_document_redaction_tracks_request_trace_and_audit():
    file_text = b"Employee email is jane.doe@example.com and Aadhaar number is 1234-5678-9012."

    response = client.post(
        "/gateway/documents/redact",
        headers=headers,
        files={"file": ("employee-record.txt", io.BytesIO(file_text), "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["request_id"].startswith("doc-")
    assert data["tenant_id"] == _tenant_id_for_test_key()
    assert data["redacted_count"] >= 2
    assert data["findings_report"]["total_findings"] >= 2
    assert data["redacted_pdf_base64"]
    assert base64.b64decode(data["redacted_pdf_base64"]).startswith(b"%PDF")
    assert all("page" in finding for finding in data["findings"])
    assert all("confidence" in finding for finding in data["findings"])
    assert all("action_taken" in finding for finding in data["findings"])
    assert "jane.doe@example.com" not in data["redacted_text"]
    assert "1234-5678-9012" not in data["redacted_text"]
    assert any(event["agent"] == "Security Agent" for event in data["trace"])
    assert any(event["agent"] == "Audit Agent" for event in data["trace"])

    with engine.connect() as conn:
        gateway_row = conn.execute(
            text(
                """
                SELECT request_id, tenant_id, provider, model, decision
                FROM gateway_requests
                WHERE request_id = :request_id
                """
            ),
            {"request_id": data["request_id"]},
        ).fetchone()
        trace_count = conn.execute(
            text("SELECT COUNT(*) FROM agent_events WHERE request_id = :request_id"),
            {"request_id": data["request_id"]},
        ).scalar()
        audit_count = conn.execute(
            text(
                """
                SELECT COUNT(*)
                FROM audit_logs
                WHERE user_query = 'Document Redaction: employee-record.txt'
                  AND policy_type = 'document_redaction'
                """
            ),
        ).scalar()

    assert gateway_row is not None
    assert gateway_row.tenant_id == str(data["tenant_id"])
    assert gateway_row.provider == "authclaw"
    assert gateway_row.model == "document-redaction"
    assert gateway_row.decision == "REDACT"
    assert trace_count >= 5
    assert audit_count >= 1


def test_gateway_document_redaction_supports_pdf_artifact_generation():
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(72, 720, "Patient name is Rahul Sharma.")
    pdf.drawString(72, 700, "PAN is ABCDE1234F and GSTIN is 27ABCDE1234F1Z5.")
    pdf.save()
    buffer.seek(0)

    response = client.post(
        "/gateway/documents/redact",
        headers=headers,
        files={"file": ("patient-record.pdf", buffer, "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["extraction_method"] == "pdf_text"
    assert data["redacted_count"] >= 3
    assert "Rahul Sharma" not in data["redacted_text"]
    assert "ABCDE1234F" not in data["redacted_text"]
    assert "27ABCDE1234F1Z5" not in data["redacted_text"]
    assert base64.b64decode(data["redacted_pdf_base64"]).startswith(b"%PDF")
    assert any(finding["field_type"] in {"name", "pan", "gstin"} for finding in data["findings"])


def test_gateway_document_redaction_blocks_document_with_secret():
    file_text = b"Production AWS key is AKIA1234567890ABCDEF. Do not send it to a provider."

    response = client.post(
        "/gateway/documents/redact",
        headers=headers,
        files={"file": ("secret-leak.txt", io.BytesIO(file_text), "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "BLOCK"
    assert data["status"] == "blocked"
    assert "AKIA1234567890ABCDEF" not in data["redacted_text"]
    assert "AKIA1234567890ABCDEF" not in repr(data["findings"])
    assert any(finding["action_taken"] == "block" for finding in data["findings"])
