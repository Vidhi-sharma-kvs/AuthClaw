import requests
import json
import sys
from sqlalchemy import text
from database import engine

import os
import os
BASE_URL = os.getenv("AUTHCLAW_TEST_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("AUTHCLAW_TEST_API_KEY")
if not API_KEY:
    raise RuntimeError("AUTHCLAW_TEST_API_KEY environment variable is not set!")


headers = {
    "Content-Type": "application/json",
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
    else:
        print(f"PASS: Status code is {expected_status}")

def truncate_db():
    print("Truncating audit_logs table for clean test state...")
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE audit_logs RESTART IDENTITY CASCADE"))
        conn.commit()

def generate_audit_log(message):
    response = requests.post(f"{BASE_URL}/policies/reload", headers=headers)
    return response

def main():
    print_banner("STARTING PHASE 4 CRYPTOGRAPHIC AUDIT CHAIN INTEGRITY TESTS")

    # 1. Normal audit records create a valid chain
    print_banner("1. Testing Normal Audit Records Creation & Verification")
    truncate_db()

    # Generate 3 audit records
    for i in range(1, 4):
        print(f"Generating audit record {i}...")
        resp = generate_audit_log(f"Show GDPR rules part {i}")
        assert_status(resp, 200)

    # Run verification
    resp_verify = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify, 200)
    verify_data = resp_verify.json()
    print("Verify Result:", json.dumps(verify_data, indent=2))
    assert verify_data["valid"] is True, "Expected chain to be valid"
    assert verify_data["records_checked"] == 3, f"Expected 3 records checked, got {verify_data['records_checked']}"

    # Run verify summary
    resp_summary = requests.get(f"{BASE_URL}/audit/verify/summary")
    assert_status(resp_summary, 200)
    summary_data = resp_summary.json()
    print("Verify Summary:", json.dumps(summary_data, indent=2))
    assert summary_data["valid"] is True
    assert summary_data["records_checked"] == 3
    assert summary_data["last_verified_record"] > 0
    assert summary_data["latest_hash"] is not None
    assert summary_data["chain_started_at"] is not None

    # Run hash chain endpoint
    resp_chain = requests.get(f"{BASE_URL}/audit/hash-chain?limit=5")
    assert_status(resp_chain, 200)
    chain_list = resp_chain.json()
    print("Hash Chain List:", json.dumps(chain_list, indent=2))
    assert len(chain_list) == 3
    print("PASS: Normal audit records create a valid cryptographic chain")

    # 2. Manual record modification triggers verification failure
    print_banner("2. Testing Manual Record Modification")
    # Fetch first record ID
    with engine.connect() as conn:
        first_id = conn.execute(text("SELECT id FROM audit_logs ORDER BY id ASC LIMIT 1")).fetchone()[0]
        print(f"Tampering with record ID {first_id} in the database...")
        conn.execute(text("UPDATE audit_logs SET user_query = 'TAMPERED QUERY' WHERE id = :id"), {"id": first_id})
        conn.commit()

    # Verify again
    resp_verify = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify, 200)
    verify_data = resp_verify.json()
    print("Verify Result after tampering:", json.dumps(verify_data, indent=2))
    assert verify_data["valid"] is False, "Expected verification to fail after tampering"
    assert verify_data["failed_record_id"] == first_id, f"Expected failed record ID to be {first_id}"
    assert verify_data["reason"] == "hash mismatch", f"Expected reason 'hash mismatch', got {verify_data['reason']}"
    print("PASS: Manual record modification successfully detected")

    # 3. Record deletion triggers verification failure (missing ID gap)
    print_banner("3. Testing Record Deletion & Missing ID Gaps")
    truncate_db()
    
    # Generate 3 new records
    for i in range(1, 4):
        generate_audit_log(f"Test query for deletion {i}")

    # Fetch all record IDs
    with engine.connect() as conn:
        ids = [row[0] for row in conn.execute(text("SELECT id FROM audit_logs ORDER BY id ASC")).fetchall()]
    print("Database record IDs before deletion:", ids)
    delete_id = ids[1] # delete second record (creates gap between 1st and 3rd)
    
    with engine.connect() as conn:
        print(f"Deleting record ID {delete_id} from database...")
        conn.execute(text("DELETE FROM audit_logs WHERE id = :id"), {"id": delete_id})
        conn.commit()

    # Verify again
    resp_verify = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify, 200)
    verify_data = resp_verify.json()
    print("Verify Result after deletion:", json.dumps(verify_data, indent=2))
    assert verify_data["valid"] is False, "Expected verification to fail after deletion"
    assert verify_data["failed_record_id"] == ids[2], f"Expected failed record ID to be {ids[2]}"
    assert "missing record detected" in verify_data["reason"], f"Expected reason to mention missing record, got {verify_data['reason']}"
    print("PASS: Record deletion and missing ID gaps successfully detected")

    # 4. Existing audit functionality remains backward compatible
    print_banner("4. Testing Legacy Records Backward Compatibility")
    truncate_db()

    # Insert a legacy record (null hashes)
    with engine.connect() as conn:
        conn.execute(
            text("""
            INSERT INTO audit_logs (user_query, response, allowed, risk_level, approval_status, created_at, integrity_hash, previous_hash)
            VALUES ('Legacy query', 'Legacy response', true, 'LOW', 'APPROVED', NOW(), NULL, NULL)
            """)
        )
        conn.commit()

    # Generate a chained record under Phase 4
    generate_audit_log("Phase 4 query after legacy record")

    # Verify chain
    resp_verify = requests.get(f"{BASE_URL}/audit/verify")
    assert_status(resp_verify, 200)
    verify_data = resp_verify.json()
    print("Verify Result with legacy record present:", json.dumps(verify_data, indent=2))
    assert verify_data["valid"] is True, "Expected chain to be valid, skipping legacy record"
    assert verify_data["records_checked"] == 1, f"Expected 1 record checked, got {verify_data['records_checked']}"
    print("PASS: Existing legacy records are ignored during verification, maintaining full backward compatibility")

    print_banner("ALL PHASE 4 CRYPTOGRAPHIC AUDIT CHAIN TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
