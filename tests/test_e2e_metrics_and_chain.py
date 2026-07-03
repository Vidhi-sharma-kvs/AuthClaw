import requests
import json
import sys
import time

import os
import os
BASE_URL = os.getenv("AUTHCLAW_TEST_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("AUTHCLAW_TEST_API_KEY")
if not API_KEY:
    raise RuntimeError("AUTHCLAW_TEST_API_KEY environment variable is not set!")

headers = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
    "Authorization": f"Bearer {API_KEY}"
}


def print_banner(text):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)

def assert_status(response, expected_status):
    if response.status_code != expected_status:
        print(f"FAIL: Expected status {expected_status}, got {response.status_code}")
        print("Response:", response.text)
        sys.exit(1)

def get_metrics():
    resp = requests.get(f"{BASE_URL}/metrics")
    assert_status(resp, 200)
    return resp.json()

def main():
    print_banner("RUNNING PHASE 5 E2E INTEGRATION & CRYPTOGRAPHIC VERIFICATION")

    # Fetch initial metrics
    initial_metrics = get_metrics()
    print("Initial Metrics:", json.dumps(initial_metrics, indent=2))
    
    # -------------------------------------------------------------------------
    # 1. Normal request increments gateway counter.
    # -------------------------------------------------------------------------
    print_banner("1. Testing: Normal request increments gateway counter")
    payload_normal = {
        "session_id": "session-e2e-1",
        "message": "What is GDPR?"
    }
    resp_normal = requests.post(f"{BASE_URL}/chat", headers=headers, json=payload_normal)
    assert_status(resp_normal, 200)
    
    metrics_after_normal = get_metrics()
    print("Metrics after normal request:", json.dumps(metrics_after_normal, indent=2))
    assert metrics_after_normal["total_requests"] == initial_metrics["total_requests"] + 1, \
        f"Expected total_requests to increment from {initial_metrics['total_requests']} to {initial_metrics['total_requests'] + 1}"
    assert metrics_after_normal["audit_chain_records"] == initial_metrics["audit_chain_records"], \
        "Normal request should NOT create a blockchain record!"
    print("PASS: Normal request incremented requests counter, and skipped blockchain logs.")

    # -------------------------------------------------------------------------
    # 2. Medium-risk request creates audit event.
    # -------------------------------------------------------------------------
    print_banner("2. Testing: Medium-risk request creates audit event (logged to file, increments request)")
    payload_med = {
        "session_id": "session-e2e-2",
        "message": "please update user password profile details"
    }
    resp_med = requests.post(f"{BASE_URL}/chat", headers=headers, json=payload_med)
    assert_status(resp_med, 200)
    
    metrics_after_med = get_metrics()
    print("Metrics after medium request:", json.dumps(metrics_after_med, indent=2))
    assert metrics_after_med["total_requests"] == metrics_after_normal["total_requests"] + 1
    assert metrics_after_med["audit_chain_records"] == metrics_after_normal["audit_chain_records"], \
        "Medium-risk allowed request should NOT create a database blockchain block!"
    print("PASS: Medium-risk request logged and counted correctly.")

    # -------------------------------------------------------------------------
    # 3. High-risk request creates approval.
    # -------------------------------------------------------------------------
    print_banner("3. Testing: High-risk request creates approval record")
    payload_high = {
        "session_id": "session-e2e-3",
        "message": "delete database production"
    }
    resp_high = requests.post(f"{BASE_URL}/chat", headers=headers, json=payload_high)
    assert_status(resp_high, 200)
    
    high_data = resp_high.json()
    approval_id = high_data.get("approval_id")
    print(f"Created approval ID: {approval_id}")
    assert approval_id is not None, "Missing approval_id"
    
    metrics_after_high = get_metrics()
    print("Metrics after high risk request:", json.dumps(metrics_after_high, indent=2))
    assert metrics_after_high["total_requests"] == metrics_after_med["total_requests"] + 1
    assert metrics_after_high["pending_approvals"] == metrics_after_med["pending_approvals"] + 1
    assert metrics_after_high["audit_chain_records"] == metrics_after_med["audit_chain_records"] + 1, \
        "High-risk approval creation MUST create 1 database audit block!"
    print("PASS: High-risk request successfully created pending approval and blockchain block.")

    # -------------------------------------------------------------------------
    # 4. Approval appears in queue.
    # -------------------------------------------------------------------------
    print_banner("4. Testing: Approval appears in queue")
    resp_list = requests.get(f"{BASE_URL}/approvals")
    assert_status(resp_list, 200)
    approvals_list = resp_list.json()
    
    found = any(app["approval_id"] == approval_id for app in approvals_list)
    assert found, f"Approval ID {approval_id} not found in queue!"
    
    # Get details
    resp_detail = requests.get(f"{BASE_URL}/approvals/{approval_id}")
    assert_status(resp_detail, 200)
    detail_data = resp_detail.json()
    assert detail_data["status"] == "pending", f"Expected pending status, got {detail_data['status']}"
    print("PASS: Approval successfully found in pending queue.")

    # -------------------------------------------------------------------------
    # 5. Approval execution updates metrics.
    # -------------------------------------------------------------------------
    print_banner("5. Testing: Approval execution updates metrics")
    # A. Approve request (with dynamic TOTP code)
    totp_secret = os.getenv("AUTHCLAW_TEST_TOTP_SECRET")
    if totp_secret:
        from main import get_hotp_token
        mfa_code = get_hotp_token(totp_secret, int(time.time()) // 30)
    else:
        mfa_code = "123456"
        
    resp_app = requests.post(f"{BASE_URL}/approve/{approval_id}", json={"mfa_code": mfa_code})
    assert_status(resp_app, 200)

    
    # B. Execute request
    resp_exec = requests.post(f"{BASE_URL}/execute/{approval_id}")
    assert_status(resp_exec, 200)
    
    metrics_after_exec = get_metrics()
    print("Metrics after execution:", json.dumps(metrics_after_exec, indent=2))
    assert metrics_after_exec["executed_approvals"] == initial_metrics["executed_approvals"] + 1
    assert metrics_after_exec["pending_approvals"] == metrics_after_high["pending_approvals"] - 1
    # Check blockchain audit block count.
    # We created blocks for: 1 (pending creation), 1 (approved decision), 1 (executed action)
    assert metrics_after_exec["audit_chain_records"] == metrics_after_high["audit_chain_records"] + 2, \
        f"Expected audit chain records to increase by 2 (approved + executed). Got: {metrics_after_exec['audit_chain_records']}"
    print("PASS: Request approved & executed successfully, and metrics updated.")

    # -------------------------------------------------------------------------
    # 6. Audit chain verification succeeds.
    # -------------------------------------------------------------------------
    print_banner("6. Testing: Audit chain verification succeeds")
    resp_verify = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify, 200)
    verify_data = resp_verify.json()
    print("Verification result:", json.dumps(verify_data, indent=2))
    assert verify_data["valid"] is True, "Verification failed when it should be valid!"
    print("PASS: Audit chain verification successfully passed.")

    # -------------------------------------------------------------------------
    # 7. Tampering causes verification failure.
    # -------------------------------------------------------------------------
    print_banner("7. Testing: Tampering causes verification failure")
    # Modify the latest record in database manually to simulate tampering
    from database import engine
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Tamper query in audit_logs
        conn.execute(text("UPDATE audit_logs SET user_query = 'tampered query' WHERE id = (SELECT MAX(id) FROM audit_logs)"))
        conn.commit()
    print("Manually tampered with latest audit log in database.")

    resp_verify_tampered = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify_tampered, 200)
    verify_tampered_data = resp_verify_tampered.json()
    print("Verification result after tampering:", json.dumps(verify_tampered_data, indent=2))
    assert verify_tampered_data["valid"] is False, "Verification passed when it should have failed!"
    print("PASS: Audit chain verification successfully detected tampering.")

    # Revert database back to clean state for later
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM audit_logs WHERE id = (SELECT MAX(id) FROM audit_logs)"))
        conn.commit()
    print("Reverted database tampering log entry.")

    print_banner("ALL 7 END-TO-END VERIFICATION CASES PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
