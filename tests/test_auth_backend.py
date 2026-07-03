import time
import uuid

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import text

from database import engine
from main import app, create_jwt, create_refresh_token_for_user, decode_jwt, hash_password, resolve_tenant


client = TestClient(app)


def _create_tenant_user(
    tenant_name,
    tenant_email,
    password="TestPassword123",
    totp_secret="JBSWY3DPEHPK3PXP",
    mfa_enabled=True,
):
    with engine.connect() as conn:
        tenant_id = conn.execute(
            text(
                """
                INSERT INTO tenants (
                    name, domain, email,
                    email_verified, domain_verified, totp_secret
                )
                VALUES (
                    :name, :domain, :email,
                    true, true, :totp_secret
                )
                RETURNING id
                """
            ),
            {
                "name": tenant_name,
                "domain": tenant_email.split("@", 1)[1],
                "email": tenant_email,
                "totp_secret": totp_secret,
            },
        ).scalar()
        user_id = conn.execute(
            text(
                """
                INSERT INTO tenant_users (
                    tenant_id, email, password_hash, role, permissions,
                    email_verified, mfa_enabled, totp_secret, status
                )
                VALUES (
                    :tenant_id, :email, :password_hash, 'Super Admin', 'all_access',
                    true, :mfa_enabled, :totp_secret, 'active'
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": tenant_id,
                "email": tenant_email,
                "password_hash": hash_password(password),
                "mfa_enabled": mfa_enabled,
                "totp_secret": totp_secret,
            },
        ).scalar()
        conn.commit()
    return tenant_id, user_id


def test_refresh_accepts_persisted_tenant_user_token():
    tenant_name = f"refresh-tenant-{uuid.uuid4().hex}"
    tenant_email = f"{tenant_name}@authclaw.local"
    tenant_id, user_id = _create_tenant_user(tenant_name, tenant_email)

    refresh_token = create_refresh_token_for_user(user_id, tenant_id, tenant_email)

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    payload = decode_jwt(response.json()["access_token"])
    assert payload["sub"] == tenant_email
    assert payload["tenant_id"] == tenant_id
    assert payload["user_id"] == user_id
    assert payload["role"] == "Super Admin"
    assert payload["permissions"] == "all_access"


def test_refresh_rejects_legacy_unpersisted_tenant_token():
    now_ts = int(time.time())
    refresh_token = create_jwt(
        {
            "sub": "legacy-tenant",
            "tenant_id": 999999,
            "iat": now_ts,
            "exp": now_ts + 86400,
        }
    )

    response = client.post("/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 401


def test_login_rejects_mfa_before_session_when_tenant_has_no_totp():
    tenant_name = f"no-mfa-tenant-{uuid.uuid4().hex}"
    tenant_email = f"admin@{tenant_name}.com"

    _create_tenant_user(tenant_name, tenant_email, totp_secret=None, mfa_enabled=True)

    response = client.post(
        "/auth/login",
        json={"username": tenant_email, "password": "TestPassword123"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "MFA_NOT_CONFIGURED"
    assert data["message"] == "MFA is not configured for this tenant."
    assert "session_id" not in data


def test_login_persists_mfa_session_in_database():
    tenant_name = f"mfa-session-tenant-{uuid.uuid4().hex}"
    tenant_email = f"admin@{tenant_name}.com"

    tenant_id, user_id = _create_tenant_user(tenant_name, tenant_email)

    response = client.post(
        "/auth/login",
        json={"username": tenant_email, "password": "TestPassword123"},
    )

    assert response.status_code == 200
    session_id = response.json()["session_id"]
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, step FROM auth_mfa_sessions WHERE session_id = :sid"),
            {"sid": session_id},
        ).fetchone()

    assert row is not None
    assert row[0] == tenant_email
    assert row[1] == "otp"


def test_verified_user_can_reset_password_and_login(monkeypatch):
    tenant_name = f"reset-tenant-{uuid.uuid4().hex}"
    tenant_email = f"admin@{tenant_name}.com"
    old_password = "OldPassword123!"
    new_password = "NewPassword123!"
    reset_token = f"reset-{uuid.uuid4().hex}"

    tenant_id, user_id = _create_tenant_user(
        tenant_name,
        tenant_email,
        password=old_password,
        mfa_enabled=False,
    )
    refresh_token = create_refresh_token_for_user(user_id, tenant_id, tenant_email)

    monkeypatch.setattr("main.generate_reset_token", lambda: reset_token)
    monkeypatch.setattr("main.send_password_reset_email", lambda recipient, token, org: None)

    request = client.post("/auth/password/reset-request", json={"username": tenant_email})

    assert request.status_code == 200
    assert request.json()["email_delivery"] == "sent"

    confirm = client.post(
        "/auth/password/reset-confirm",
        json={"token": reset_token, "password": new_password},
    )

    assert confirm.status_code == 200
    assert confirm.json()["email"] == tenant_email

    old_login = client.post("/auth/login", json={"username": tenant_email, "password": old_password})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"username": tenant_email, "password": new_password})
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]

    reused = client.post(
        "/auth/password/reset-confirm",
        json={"token": reset_token, "password": "AnotherPassword123!"},
    )
    assert reused.status_code == 400

    refresh = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401


def test_password_reset_local_debug_for_unknown_account(monkeypatch):
    monkeypatch.setenv("AUTHCLAW_ENV", "development")
    email = f"missing-{uuid.uuid4().hex}@authclaw.local"

    response = client.post("/auth/password/reset-request", json={"username": email})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["email_delivery"] == "not_attempted"
    assert "No active tenant user exists" in payload["local_debug"]
    assert "reset_token" not in payload


def test_login_reports_pending_registration_verification_state():
    email = f"pending-{uuid.uuid4().hex}@authclaw.local"
    email_token = f"email-{uuid.uuid4().hex}"
    domain_token = f"authclaw-domain-verification={uuid.uuid4().hex}"

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO onboarding_registrations (
                    organization_name, full_name, work_email, domain, password_hash,
                    email_verification_token, domain_verification_token, totp_secret
                )
                VALUES (
                    :organization_name, :full_name, :work_email, :domain, :password_hash,
                    :email_token, :domain_token, :totp_secret
                )
                """
            ),
            {
                "organization_name": "Pending AuthClaw Tenant",
                "full_name": "Pending Admin",
                "work_email": email,
                "domain": "authclaw.local",
                "password_hash": hash_password("PendingPassword123!"),
                "email_token": email_token,
                "domain_token": domain_token,
                "totp_secret": "JBSWY3DPEHPK3PXP",
            },
        )
        conn.commit()

    response = client.post(
        "/auth/login",
        json={"username": email, "password": "PendingPassword123!"},
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "Email not verified"
    assert payload["email_verified"] is False
    assert payload["email_token"] == email_token
    assert payload["domain_token"] == domain_token


def test_generated_api_key_can_be_soft_revoked():
    tenant_name = f"api-key-tenant-{uuid.uuid4().hex}"
    tenant_email = f"admin@{tenant_name}.com"

    tenant_id, user_id = _create_tenant_user(tenant_name, tenant_email)

    token = create_jwt(
        {
            "sub": tenant_name,
            "tenant_id": tenant_id,
            "role": "Super Admin",
            "permissions": "all_access",
            "user_id": user_id,
            "iat": int(time.time()),
            "exp": int(time.time()) + 900,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    generated = client.post("/keys/generate", headers=headers, json={"name": "Production key"})

    assert generated.status_code == 200
    raw_key = generated.json()["api_key"]
    assert generated.json()["expires_at"]
    assert resolve_tenant(raw_key) == tenant_id

    listed = client.get("/keys/list", headers=headers)
    assert listed.status_code == 200
    key_id = listed.json()[0]["id"]
    assert listed.json()[0]["status"] == "active"

    revoked = client.delete(f"/keys/{key_id}", headers=headers)
    assert revoked.status_code == 200

    with pytest.raises(HTTPException) as exc:
        resolve_tenant(raw_key)
    assert exc.value.status_code == 401
