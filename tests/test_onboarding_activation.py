import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

import main
from database import engine


client = TestClient(main.app)


class _TxtRecord:
    def __init__(self, token):
        self.strings = [token.encode("utf-8")]


def test_registration_activates_tenant_only_after_email_and_domain_verification(monkeypatch):
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "false")
    monkeypatch.setenv("SKIP_DOMAIN_VERIFICATION", "false")
    sent = []
    monkeypatch.setattr(main, "send_verification_email", lambda recipient, token, org: sent.append((recipient, token, org)))

    suffix = uuid.uuid4().hex[:10]
    email = f"admin-{suffix}@phasec.example"
    domain = f"phasec-{suffix}.example"
    organization_name = f"PhaseC {suffix}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": organization_name,
            "full_name": "Phase C Admin",
            "email": email,
            "password": "StrongPassword123!",
            "domain": domain,
        },
    )

    assert register_response.status_code == 200
    assert sent and sent[0][0] == email
    assert "email_token" not in register_response.json()

    with engine.connect() as conn:
        pending = conn.execute(
            text("""
                SELECT id, email_verification_token, domain_verification_token, tenant_id
                FROM onboarding_registrations
                WHERE work_email = :email
            """),
            {"email": email},
        ).fetchone()
        assert pending is not None
        assert pending[3] is None
        assert conn.execute(text("SELECT COUNT(*) FROM tenants WHERE email = :email"), {"email": email}).scalar() == 0

    verify_email = client.post("/auth/verify-email", json={"token": pending[1]})
    assert verify_email.status_code == 200

    def resolve_txt(self, qname, rdtype="A", *args, **kwargs):
        assert rdtype == "TXT"
        assert str(qname) == domain
        return [_TxtRecord(pending[2])]

    import dns.resolver

    monkeypatch.setattr(dns.resolver.Resolver, "resolve", resolve_txt)
    verify_domain = client.post("/auth/verify-domain", json={"domain": domain, "token": pending[2]})
    assert verify_domain.status_code == 200
    tenant_id = verify_domain.json()["tenant_id"]

    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT id, email_verified, domain_verified FROM tenants WHERE id = :id"),
            {"id": tenant_id},
        ).fetchone()
        user = conn.execute(
            text("SELECT email, email_verified, role FROM tenant_users WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        ).fetchone()

    assert tenant is not None
    assert tenant[1] is True
    assert tenant[2] is True
    assert user[0] == email
    assert user[1] is True
    assert user[2] == "Super Admin"


def test_testing_bypass_activates_tenant_after_email_verification(monkeypatch):
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "true")
    monkeypatch.setenv("SKIP_DOMAIN_VERIFICATION", "true")
    monkeypatch.setenv("DISABLE_MFA_FOR_TESTING", "false")

    suffix = uuid.uuid4().hex[:10]
    email = f"admin-{suffix}@localtest.example"
    domain = f"localtest-{suffix}.example"
    organization_name = f"Local Test {suffix}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": organization_name,
            "full_name": "Local Test Admin",
            "email": email,
            "password": "StrongPassword123!",
            "domain": domain,
        },
    )

    assert register_response.status_code == 200
    register_data = register_response.json()
    assert register_data["email_delivery"] == "skipped_for_testing"
    assert register_data["email_token"]

    verify_email = client.post("/auth/verify-email", json={"token": register_data["email_token"]})

    assert verify_email.status_code == 200
    verify_data = verify_email.json()
    assert verify_data["activated"] is True
    assert verify_data["domain_verification_skipped"] is True

    with engine.connect() as conn:
        tenant = conn.execute(
            text("SELECT id, email_verified, domain_verified FROM tenants WHERE email = :email"),
            {"email": email},
        ).fetchone()
        user = conn.execute(
            text("SELECT email, email_verified, role FROM tenant_users WHERE email = :email"),
            {"email": email},
        ).fetchone()

    assert tenant is not None
    assert tenant[1] is True
    assert tenant[2] is True
    assert user[0] == email
    assert user[1] is True
    assert user[2] == "Super Admin"


def test_local_manual_testing_allows_shared_domain_and_password_login(monkeypatch):
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "true")
    monkeypatch.setenv("SKIP_DOMAIN_VERIFICATION", "true")
    monkeypatch.setenv("DISABLE_MFA_FOR_TESTING", "true")

    suffix = uuid.uuid4().hex[:10]
    shared_domain = "google.com"
    emails = [
        f"admin-{suffix}-a@manual.example",
        f"admin-{suffix}-b@manual.example",
    ]

    for email in emails:
        register_response = client.post(
            "/auth/register",
            json={
                "name": f"Manual Test {suffix} {email[6]}",
                "full_name": "Manual Test Admin",
                "email": email,
                "password": "StrongPassword123!",
                "domain": shared_domain,
            },
        )

        assert register_response.status_code == 200
        email_token = register_response.json()["email_token"]

        verify_email = client.post("/auth/verify-email", json={"token": email_token})
        assert verify_email.status_code == 200
        assert verify_email.json()["activated"] is True

        login = client.post(
            "/auth/login",
            json={"username": email, "password": "StrongPassword123!"},
        )
        assert login.status_code == 200
        assert login.json()["access_token"]
        assert login.json()["user"]["email_verified"] is True
        assert login.json()["user"]["domain_verified"] is True


def test_default_policies_and_provider_list_are_available_for_new_tenant(monkeypatch):
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "true")
    monkeypatch.setenv("SKIP_DOMAIN_VERIFICATION", "true")
    monkeypatch.setenv("DISABLE_MFA_FOR_TESTING", "true")

    suffix = uuid.uuid4().hex[:10]
    email = f"admin-{suffix}@tenant.example"
    password = "StrongPassword123!"

    register_response = client.post(
        "/auth/register",
        json={
            "name": f"Tenant Defaults {suffix}",
            "full_name": "Tenant Defaults Admin",
            "email": email,
            "password": password,
            "domain": "google.com",
        },
    )
    assert register_response.status_code == 200

    verify_email = client.post("/auth/verify-email", json={"token": register_response.json()["email_token"]})
    assert verify_email.status_code == 200

    login = client.post("/auth/login", json={"username": email, "password": password})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    policies = client.get("/policies/list", headers=headers)
    assert policies.status_code == 200
    policy_names = {policy["name"] for policy in policies.json()}
    assert {"PII Protection", "Prompt Injection Defense", "Secrets Exfiltration Guard"}.issubset(policy_names)

    providers = client.get("/providers/list", headers=headers)
    assert providers.status_code == 200
    assert providers.json() == []
