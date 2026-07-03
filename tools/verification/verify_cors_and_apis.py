import requests
import json
import sys

import os
import os
BASE_URL = os.getenv("AUTHCLAW_TEST_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("AUTHCLAW_TEST_API_KEY")
if not API_KEY:
    raise RuntimeError("AUTHCLAW_TEST_API_KEY environment variable is not set!")


def print_banner(text):
    print("\n" + "=" * 80)
    print(f" {text}")
    print("=" * 80)

def verify_cors_headers(url, method="GET"):
    print(f"Checking CORS preflight for {method} {url}...")
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "content-type, x-api-key, authorization",
    }
    response = requests.options(url, headers=headers)
    print(f"Preflight status: {response.status_code}")
    print("Headers:", dict(response.headers))
    
    allow_origin = response.headers.get("Access-Control-Allow-Origin")
    if allow_origin not in ("http://localhost:5173", "*"):
        print(f"FAIL: Access-Control-Allow-Origin header is incorrect: {allow_origin}")
        sys.exit(1)
    print("PASS: CORS preflight check passed!")

def test_health_endpoints():
    print_banner("Testing health endpoints")
    
    # Test GET /health
    print("Testing GET /health...")
    resp = requests.get(f"{BASE_URL}/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    print("GET /health response:", data)
    assert data == {"status": "healthy"}, f"Expected status healthy, got {data}"
    print("PASS: GET /health works!")

    # Test GET /health/details
    print("Testing GET /health/details...")
    resp = requests.get(f"{BASE_URL}/health/details")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    print("GET /health/details response:", json.dumps(data, indent=2))
    required_keys = [
        "audit_chain_active",
        "hitl_enabled",
        "policy_enforcement_enabled",
        "redaction_enabled",
        "provider_status",
        "database_status"
    ]
    for key in required_keys:
        assert key in data, f"Missing key '{key}' in health details"
    print("PASS: GET /health/details works!")

def test_policy_reload():
    print_banner("Testing policy reload")
    
    # Test POST /policies/reload
    print("Testing POST /policies/reload...")
    resp = requests.post(f"{BASE_URL}/policies/reload")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    print("POST /policies/reload response:", data.get("message"))
    assert "reloaded successfully" in data.get("message", "").lower()
    print("PASS: Policy reload works!")

def main():
    print_banner("STARTING PHASE 5 ENTERPRISE INTEGRATION VERIFICATION")
    
    # Check CORS
    verify_cors_headers(f"{BASE_URL}/health", "GET")
    verify_cors_headers(f"{BASE_URL}/policies/reload", "POST")
    verify_cors_headers(f"{BASE_URL}/chat", "POST")
    
    # Check APIs
    test_health_endpoints()
    test_policy_reload()
    
    print_banner("ALL PHASE 5 BACKEND API & CORS CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    main()
