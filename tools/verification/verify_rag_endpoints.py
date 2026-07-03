import requests

import os

BASE_URL = os.getenv("AUTHCLAW_TEST_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("AUTHCLAW_TEST_API_KEY")
if not API_KEY:
    raise RuntimeError("AUTHCLAW_TEST_API_KEY environment variable is not set!")
HEADERS = {
    "x-api-key": API_KEY
}


def verify_all():
    print("=== START RAG & COMPLIANCE VERIFICATION ===")
    
    # 1. Test upload
    print("\n1. Testing POST /documents/upload...")
    file_content = (
        "AuthClaw security and data protection policies.\n"
        "Data Encryption: All data transmitted is encrypted using TLS 1.3. Data at rest is encrypted with AES-256.\n"
        "Access Control: We enforce role-based access control (RBAC) and follow least privilege.\n"
        "Multi-Factor Authentication: MFA is required for all admin accounts.\n"
        "Data Retention: Customer PII is retained for exactly 7 years and then securely deleted.\n"
        "Audit Logging: Security logs are collected and audited weekly.\n"
        "Consent: We obtain explicit user consent before storing personal details."
    )
    
    files = {
        "file": ("test_security_policy.txt", file_content.encode("utf-8"), "text/plain")
    }
    
    res = requests.post(f"{BASE_URL}/documents/upload", headers=HEADERS, files=files)
    print("Response Status:", res.status_code)
    print("Response JSON:", res.json())
    assert res.status_code == 200, "Upload failed"
    doc_id = res.json()["document_id"]
    assert doc_id.startswith("doc_"), "Invalid doc ID format"
    
    # 2. Test compliance analyze
    print("\n2. Testing POST /compliance/analyze...")
    analyze_payload = {
        "document_id": doc_id
    }
    res_analyze = requests.post(f"{BASE_URL}/compliance/analyze", headers=HEADERS, json=analyze_payload)
    print("Response Status:", res_analyze.status_code)
    analysis = res_analyze.json()
    print("SOC2 Score:", analysis.get("soc2_score"))
    print("GDPR Score:", analysis.get("gdpr_score"))
    print("HIPAA Score:", analysis.get("hipaa_score"))
    print("ISO 27001 Score:", analysis.get("iso27001_score"))
    print("Overall Risk:", analysis.get("overall_risk"))
    print("Executive Summary:", analysis.get("executive_summary"))
    print("Findings Count:", len(analysis.get("findings", [])))
    assert res_analyze.status_code == 200, "Compliance analysis failed"
    
    # 3. Test copilot chat
    print("\n3. Testing POST /documents/chat...")
    chat_payload = {
        "document_id": doc_id,
        "question": "What encryption standard is defined?"
    }
    res_chat = requests.post(f"{BASE_URL}/documents/chat", headers=HEADERS, json=chat_payload)
    print("Response Status:", res_chat.status_code)
    chat_data = res_chat.json()
    print("Answer:", chat_data.get("answer"))
    print("Citations Count:", len(chat_data.get("citations", [])))
    assert res_chat.status_code == 200, "Document chat failed"
    
    # 4. Test evidence list
    print("\n4. Testing GET /evidence...")
    res_ev = requests.get(f"{BASE_URL}/evidence", headers=HEADERS)
    print("Response Status:", res_ev.status_code)
    evidences = res_ev.json()
    print("Total Evidence in Vault:", len(evidences))
    # Find our generated reports
    our_reports = [e for e in evidences if doc_id in e.get("file_path", "")]
    print(f"Generated Reports for {doc_id} in vault: {len(our_reports)}")
    assert len(our_reports) >= 3, "Evidence reports not stored in vault"
    
    # 5. Test evidence download
    print("\n5. Testing GET /evidence/download/{filename}...")
    filename = our_reports[0]["file_path"].replace("/evidence/", "")
    res_dl = requests.get(f"{BASE_URL}/evidence/download/{filename}", headers=HEADERS)
    print("Response Status:", res_dl.status_code)
    print("File Content Preview:\n", res_dl.text[:200])
    assert res_dl.status_code == 200, "Download failed"
    
    print("\n=== ALL TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    verify_all()
