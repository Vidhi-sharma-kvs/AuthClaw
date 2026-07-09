import uuid
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import (
    app,
    create_jwt,
    skip_domain_verification_for_testing,
    skip_email_delivery_for_testing,
)
from services.enterprise_identity import pkce_challenge


client = TestClient(app)


def _create_tenant(name: str) -> int:
    with engine.connect() as conn:
        tenant_id = conn.execute(
            text(
                """
                INSERT INTO tenants (name, domain, email, email_verified, domain_verified)
                VALUES (:name, :domain, :email, true, true)
                RETURNING id
                """
            ),
            {
                "name": name,
                "domain": f"{name.lower()}.example",
                "email": f"admin@{name.lower()}.example",
            },
        ).scalar()
        conn.commit()
    return tenant_id


def _tenant_admin_header(tenant_id: int) -> dict:
    token = create_jwt(
        {
            "sub": f"admin-{tenant_id}@authclaw.local",
            "email": f"admin-{tenant_id}@authclaw.local",
            "tenant_id": tenant_id,
            "user_id": tenant_id,
            "role": "Super Admin",
            "permissions": "all_access",
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _oidc_payload() -> dict:
    return {
        "provider_type": "generic_oidc",
        "display_name": "Pytest OIDC",
        "client_id": f"client-{uuid.uuid4().hex}",
        "client_secret": f"secret-{uuid.uuid4().hex}",
        "issuer": "https://idp.example.com",
        "authorization_endpoint": "https://idp.example.com/oauth2/v1/authorize",
        "token_endpoint": "https://idp.example.com/oauth2/v1/token",
        "userinfo_endpoint": "https://idp.example.com/oauth2/v1/userinfo",
        "jwks_uri": "https://idp.example.com/oauth2/v1/keys",
        "redirect_uri": "https://app.authclaw.example.com/auth/oidc/callback",
        "groups_claim": "groups",
        "role_mapping": {"security-team": "Security Admin", "*": "Developer"},
        "enabled": True,
    }


def test_pkce_challenge_is_s256_urlsafe():
    challenge = pkce_challenge("phase1-test-verifier")

    assert challenge
    assert "=" not in challenge
    assert "+" not in challenge
    assert "/" not in challenge


def test_production_disables_local_auth_bypasses(monkeypatch):
    monkeypatch.setenv("AUTHCLAW_ENV", "production")
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "true")
    monkeypatch.setenv("SKIP_DOMAIN_VERIFICATION", "true")

    assert skip_email_delivery_for_testing() is False
    assert skip_domain_verification_for_testing() is False


def test_https_enforcement_preserves_local_and_redirects_external(monkeypatch):
    monkeypatch.setenv("AUTHCLAW_ENFORCE_HTTPS", "true")

    local_response = client.get("/health", headers={"host": "127.0.0.1:8000", "x-forwarded-proto": "http"})
    assert local_response.status_code == 200

    redirect_response = client.get(
        "/health",
        headers={"host": "app.authclaw.example.com", "x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert redirect_response.status_code == 308
    assert redirect_response.headers["location"].startswith("https://app.authclaw.example.com")

    secure_response = client.get(
        "/health",
        headers={"host": "app.authclaw.example.com", "x-forwarded-proto": "https"},
    )
    assert secure_response.status_code == 200
    assert "max-age=31536000" in secure_response.headers["strict-transport-security"]


def test_tenant_identity_provider_config_is_encrypted_and_tenant_scoped():
    tenant_id = _create_tenant(f"OIDCIso{uuid.uuid4().hex[:8]}")
    payload = _oidc_payload()

    try:
        response = client.post("/identity/providers", json=payload, headers=_tenant_admin_header(tenant_id))
        assert response.status_code == 200
        provider_id = response.json()["id"]

        listed = client.get("/identity/providers", headers=_tenant_admin_header(tenant_id))
        assert listed.status_code == 200
        providers = listed.json()
        assert providers[0]["id"] == provider_id
        assert "client_secret" not in providers[0]
        assert providers[0]["role_mapping"]["security-team"] == "Security Admin"

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT encrypted_client_secret
                    FROM tenant_identity_providers
                    WHERE id = :provider_id AND tenant_id = :tenant_id
                    """
                ),
                {"provider_id": provider_id, "tenant_id": tenant_id},
            ).fetchone()
        assert row is not None
        assert row[0] != payload["client_secret"]
        assert payload["client_secret"] not in row[0]
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM tenants WHERE id = :tenant_id"), {"tenant_id": tenant_id})
            conn.commit()


def test_oidc_login_creates_state_and_pkce_authorization_url():
    tenant_id = _create_tenant(f"OIDCLogin{uuid.uuid4().hex[:8]}")
    payload = _oidc_payload()

    try:
        provider_id = client.post(
            "/identity/providers",
            json=payload,
            headers=_tenant_admin_header(tenant_id),
        ).json()["id"]

        response = client.get(f"/auth/oidc/login?tenant_id={tenant_id}&provider_id={provider_id}")
        assert response.status_code == 200
        data = response.json()
        parsed = urlparse(data["authorization_url"])
        params = parse_qs(parsed.query)

        assert parsed.scheme == "https"
        assert params["client_id"] == [payload["client_id"]]
        assert params["code_challenge_method"] == ["S256"]
        assert params["state"] == [data["state"]]
        assert data["pkce"]["method"] == "S256"
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM tenants WHERE id = :tenant_id"), {"tenant_id": tenant_id})
            conn.commit()


def test_phase1_rls_policies_exist_for_identity_tables():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND policyname LIKE 'tenant_isolation_%'
                  AND tablename IN (
                    'tenant_identity_providers',
                    'oidc_login_states',
                    'oidc_jwks_cache',
                    'oidc_user_sessions'
                  )
                """
            )
        ).fetchall()

    assert {
        "tenant_identity_providers",
        "oidc_login_states",
        "oidc_jwks_cache",
        "oidc_user_sessions",
    }.issubset({row[0] for row in rows})
