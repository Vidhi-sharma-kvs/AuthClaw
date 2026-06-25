import os
import sys
import uuid
import hashlib
import base64
import time
import subprocess
import requests
from sqlalchemy import create_engine, text

def run_tests():
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 80)
    print("AuthClaw Testing Infrastructure - run_test_server.py")
    print("=" * 80)


    # 1. Set environment variables
    test_db_url = "postgresql://postgres:vidhi@localhost:5432/authclaw_test"
    os.environ["DATABASE_URL"] = test_db_url
    os.environ["GOOGLE_API_KEY"] = "dummy"

    # 2. Re-create the database authclaw_test
    print("Re-creating test database...")
    postgres_url = "postgresql://postgres:vidhi@localhost:5432/postgres"
    postgres_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    with postgres_engine.connect() as conn:
        conn.execute(text("DROP DATABASE IF EXISTS authclaw_test"))
        conn.execute(text("CREATE DATABASE authclaw_test"))

    # 3. Run database migrations to populate tables
    print("Running database migrations...")
    from database.migrations import run_startup_migrations
    run_startup_migrations()

    # 4. Create a dynamic test tenant and dynamic API key
    print("Creating dynamic test tenant...")
    from main import hash_password
    tenant_name = f"test-tenant-{uuid.uuid4().hex[:12]}"
    tenant_domain = f"{tenant_name}.com"
    tenant_email = f"admin@{tenant_domain}"
    tenant_password = "TestPassword123"
    password_hash = hash_password(tenant_password)

    email_token = str(uuid.uuid4())
    domain_token = f"authclaw-domain-verification={uuid.uuid4().hex[:16]}"
    totp_secret = base64.b32encode(os.urandom(10)).decode('utf-8')

    from database import engine
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            INSERT INTO tenants (name, domain, email, password_hash, email_verified, email_verification_token, domain_verified, domain_verification_token, totp_secret)
            VALUES (:name, :domain, :email, :password, true, :et, true, :dt, :totp)
            RETURNING id
            """),
            {
                "name": tenant_name,
                "domain": tenant_domain,
                "email": tenant_email,
                "password": password_hash,
                "et": email_token,
                "dt": domain_token,
                "totp": totp_secret
            }
        )
        tenant_id = res.fetchone()[0]
        conn.commit()

    # Generate a random API key
    test_api_key = f"test-key-{uuid.uuid4().hex[:12]}"
    key_hash = hashlib.sha256(test_api_key.encode('utf-8')).hexdigest()

    print(f"Generated dynamic test API key: {test_api_key}")
    print(f"Generated dynamic TOTP secret: {totp_secret}")

    with engine.connect() as conn:
        conn.execute(
            text("INSERT INTO tenant_api_keys (tenant_id, name, key_hash) VALUES (:tid, 'Test Key', :hash)"),
            {"tid": tenant_id, "hash": key_hash}
        )
        # Seed active compliance policies for this tenant
        conn.execute(
            text("""
            INSERT INTO policies (name, type, rules, enabled, tenant_id)
            VALUES 
            ('GDPR Policy', 'GDPR', '{"blocked_keywords": ["passport", "ssn", "social security number"], "pii_redaction": true}', true, :tid),
            ('SOC2 Policy', 'SOC2', '{"blocked_keywords": ["credit card", "bank routing", "pin number"], "pii_redaction": true}', true, :tid),
            ('HIPAA Policy', 'HIPAA', '{"blocked_keywords": ["medical record", "health history", "diagnoses", "diagnosis"], "pii_redaction": true}', true, :tid)
            """),
            {"tid": tenant_id}
        )
        conn.commit()

    # Dispose of migrations engine so it doesn't leak connections
    engine.dispose()

    # 5. Start FastAPI server
    print("Starting backend server on port 8050...")
    env = os.environ.copy()
    env["AUTHCLAW_TEST_API_KEY"] = test_api_key
    env["AUTHCLAW_TEST_TOTP_SECRET"] = totp_secret
    env["DATABASE_URL"] = test_db_url
    env["GOOGLE_API_KEY"] = "dummy"
    env["AUTHCLAW_TEST_URL"] = "http://127.0.0.1:8050"

    # Start uvicorn as a background process writing to a log file to prevent PIPE deadlock
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    server_log_path = os.path.join(log_dir, "test_server_output.log")
    server_log = open(server_log_path, "w", encoding="utf-8")

    server_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--port", "8050", "--host", "127.0.0.1"]
    server_process = subprocess.Popen(
        server_cmd,
        env=env,
        stdout=server_log,
        stderr=server_log
    )

    # Helper to check if server is up
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
            with open(server_log_path, "r", encoding="utf-8") as f:
                print("Server Log:\n", f.read())
        except Exception:
            pass
        sys.exit(1)

    server_log.close()


    # 6. Run all integration verification scripts
    scripts = [
        "verify_security.py",
        "verify_cors_and_apis.py",
        "verify_rag_endpoints.py",
        "test_e2e_metrics_and_chain.py",
        "test_hitl_workflow.py",
        "final_verify.py",
        "test_gateway.py",
        "test_audit_chain.py"
    ]

    failed_scripts = []

    for script in scripts:
        print(f"\nRunning integration script: {script} ...")
        script_path = os.path.join(os.getcwd(), script)
        res = subprocess.run(
            [sys.executable, script_path],
            env=env,
            capture_output=True,
            text=True
        )
        print(res.stdout)
        if res.returncode != 0:
            print(f"ERROR: Script {script} failed with exit code {res.returncode}")
            print(res.stderr)
            failed_scripts.append(script)
        else:
            print(f"PASS: Script {script} completed successfully.")

    # 7. Cleanup & Tear Down
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
        print(f"\n⚠️ Verification failed! The following scripts failed: {failed_scripts}")
        sys.exit(1)
    else:
        print("\n🎉 SUCCESS: All integration scripts passed successfully against isolated test server!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
