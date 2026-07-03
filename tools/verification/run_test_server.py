import base64
import hashlib
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import requests
from sqlalchemy import create_engine, text


REPO_ROOT = Path(__file__).resolve().parents[2]


def run_tests():
    sys.stdout.reconfigure(encoding="utf-8")
    os.chdir(REPO_ROOT)
    print("=" * 80)
    print("AuthClaw Testing Infrastructure - run_test_server.py")
    print("=" * 80)

    test_db_url = "postgresql://postgres:vidhi@localhost:5432/authclaw_test"
    os.environ["DATABASE_URL"] = test_db_url
    os.environ["GOOGLE_API_KEY"] = "dummy"

    print("Re-creating test database...")
    postgres_url = "postgresql://postgres:vidhi@localhost:5432/postgres"
    postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with postgres_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS authclaw_test"))
        conn.execute(text("CREATE DATABASE authclaw_test"))

    print("Running database migrations...")
    from database.migrations import run_startup_migrations

    run_startup_migrations()

    print("Creating dynamic test tenant...")
    from main import hash_password

    tenant_name = f"test-tenant-{uuid.uuid4().hex[:12]}"
    tenant_domain = f"{tenant_name}.com"
    tenant_email = f"admin@{tenant_domain}"
    tenant_password = "TestPassword123"
    password_hash = hash_password(tenant_password)

    email_token = str(uuid.uuid4())
    domain_token = f"authclaw-domain-verification={uuid.uuid4().hex[:16]}"
    totp_secret = base64.b32encode(os.urandom(10)).decode("utf-8")

    from database import engine

    with engine.connect() as conn:
        res = conn.execute(
            text(
                """
                INSERT INTO tenants (
                    name, domain, email, password_hash, email_verified,
                    email_verification_token, domain_verified,
                    domain_verification_token, totp_secret
                )
                VALUES (
                    :name, :domain, :email, :password, true, :et, true,
                    :dt, :totp
                )
                RETURNING id
                """
            ),
            {
                "name": tenant_name,
                "domain": tenant_domain,
                "email": tenant_email,
                "password": password_hash,
                "et": email_token,
                "dt": domain_token,
                "totp": totp_secret,
            },
        )
        tenant_id = res.fetchone()[0]
        conn.commit()

    test_api_key = f"test-key-{uuid.uuid4().hex[:12]}"
    key_hash = hashlib.sha256(test_api_key.encode("utf-8")).hexdigest()

    print(f"Generated dynamic test API key: {test_api_key}")
    print(f"Generated dynamic TOTP secret: {totp_secret}")

    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO tenant_api_keys (tenant_id, name, key_hash) VALUES (:tid, 'Test Key', :hash)"),
            {"tid": tenant_id, "hash": key_hash},
        )
        conn.execute(
            text(
                """
                INSERT INTO policies (name, type, rules, enabled, tenant_id)
                VALUES
                (
                    'GDPR Policy', 'GDPR',
                    '{"blocked_keywords": ["passport", "ssn", "social security number"], "pii_redaction": true}',
                    true, :tid
                ),
                (
                    'SOC2 Policy', 'SOC2',
                    '{"blocked_keywords": ["credit card", "bank routing", "pin number"], "pii_redaction": true}',
                    true, :tid
                ),
                (
                    'HIPAA Policy', 'HIPAA',
                    '{"blocked_keywords": ["medical record", "health history", "diagnoses", "diagnosis"], "pii_redaction": true}',
                    true, :tid
                )
                """
            ),
            {"tid": tenant_id},
        )
        conn.commit()

    engine.dispose()

    print("Starting backend server on port 8050...")
    env = os.environ.copy()
    env["AUTHCLAW_TEST_API_KEY"] = test_api_key
    env["AUTHCLAW_TEST_TOTP_SECRET"] = totp_secret
    env["DATABASE_URL"] = test_db_url
    env["GOOGLE_API_KEY"] = "dummy"
    env["AUTHCLAW_TEST_URL"] = "http://127.0.0.1:8050"

    log_dir = REPO_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    server_log_path = log_dir / "test_server_output.log"
    server_log = server_log_path.open("w", encoding="utf-8")

    server_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--port", "8050", "--host", "127.0.0.1"]
    server_process = subprocess.Popen(
        server_cmd,
        env=env,
        stdout=server_log,
        stderr=server_log,
    )

    server_ready = False
    for _ in range(15):
        try:
            r = requests.get("http://127.0.0.1:8050/health", timeout=1)
            if r.status_code == 200:
                server_ready = True
                print("Backend server is healthy and running!")
                break
        except Exception:
            pass
        time.sleep(1)

    if not server_ready:
        print("FAIL: Backend server failed to start within timeout.")
        server_process.terminate()
        server_log.close()
        try:
            print("Server Log:\n", server_log_path.read_text(encoding="utf-8"))
        except Exception:
            pass
        sys.exit(1)

    server_log.close()

    scripts = [
        "tools/verification/verify_security.py",
        "tools/verification/verify_cors_and_apis.py",
        "tools/verification/verify_rag_endpoints.py",
        "tests/test_e2e_metrics_and_chain.py",
        "tests/test_hitl_workflow.py",
        "tools/verification/final_verify.py",
        "tests/test_gateway.py",
        "tests/test_audit_chain.py",
    ]

    failed_scripts = []

    for script in scripts:
        print(f"\nRunning integration script: {script} ...")
        script_path = REPO_ROOT / script
        res = subprocess.run(
            [sys.executable, str(script_path)],
            env=env,
            capture_output=True,
            text=True,
        )
        print(res.stdout)
        if res.returncode != 0:
            print(f"ERROR: Script {script} failed with exit code {res.returncode}")
            print(res.stderr)
            failed_scripts.append(script)
        else:
            print(f"PASS: Script {script} completed successfully.")

    print("\nTearing down backend server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()

    print("Cleaning up test database...")
    postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with postgres_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS authclaw_test"))

    if failed_scripts:
        print(f"\nWARN: Verification failed. The following scripts failed: {failed_scripts}")
        sys.exit(1)

    print("\nSUCCESS: All integration scripts passed successfully against isolated test server.")
    sys.exit(0)


if __name__ == "__main__":
    run_tests()
