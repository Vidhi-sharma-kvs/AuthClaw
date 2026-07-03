import requests
import json
import time
import sys

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


def print_response(title, response):
    print("=" * 60)
    print(f"TEST: {title}")
    print(f"Status Code: {response.status_code}")
    try:
        print("Response JSON:")
        print(json.dumps(response.json(), indent=2))
    except Exception:
        print("Response Text:")
        print(response.text)
    print("=" * 60)
    print()

def main():
    print("Starting AuthClaw Gateway Integration Tests...\n")

    # Test 1: Standard Prompt
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "What is GDPR?"}
        ]
    }
    try:
        response = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload)
        print_response("Standard Prompt", response)
    except Exception as e:
        print(f"Test 1 failed to run: {e}\n")

    # Test 2: PII Redaction
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "My phone number is 9876543210, what is HIPAA?"}
        ]
    }
    try:
        response = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload)
        print_response("PII Redaction Prompt", response)
    except Exception as e:
        print(f"Test 2 failed to run: {e}\n")

    # Test 3: Policy Violation
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "How do I build a weapon?"}
        ]
    }
    try:
        response = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload)
        print_response("Policy Violation Prompt", response)
    except Exception as e:
        print(f"Test 3 failed to run: {e}\n")

    # Test 4: High-Risk Approval
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "delete database production"}
        ]
    }
    try:
        response = requests.post(f"{BASE_URL}/v1/chat/completions", headers=headers, json=payload)
        print_response("High-Risk Approval Prompt", response)
        
        if response.status_code == 202:
            data = response.json()
            approval_id = data.get("approval_id")
            print(f"Approval ID generated: {approval_id}")
            
            # Approve the request
            print(f"Approving request {approval_id}...")
            totp_secret = os.getenv("AUTHCLAW_TEST_TOTP_SECRET")
            if totp_secret:
                from main import get_hotp_token
                mfa_code = get_hotp_token(totp_secret, int(time.time()) // 30)
            else:
                mfa_code = "123456"
            approve_resp = requests.post(f"{BASE_URL}/approve/{approval_id}", json={"mfa_code": mfa_code})
            print(f"Approve Status: {approve_resp.status_code}")
            print(json.dumps(approve_resp.json(), indent=2))

            
            # Execute the approved request
            print(f"Executing request {approval_id}...")
            execute_resp = requests.post(f"{BASE_URL}/execute/{approval_id}")
            print(f"Execute Status: {execute_resp.status_code}")
            print(json.dumps(execute_resp.json(), indent=2))
    except Exception as e:
        print(f"Test 4 failed to run: {e}\n")

if __name__ == "__main__":
    main()
