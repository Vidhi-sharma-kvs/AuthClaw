import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from database.migrations import run_startup_migrations
from main import app, create_jwt
from services.provider_router import ProviderRouter
from services.secret_manager import SecretManager


client = TestClient(app)
_schema_ready = False


def _ensure_schema():
    global _schema_ready
    if not _schema_ready:
        run_startup_migrations()
        _schema_ready = True


def _create_test_tenant() -> int:
    _ensure_schema()
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO tenants (name, status, email_verified, domain_verified)
                VALUES (:name, 'active', TRUE, TRUE)
                RETURNING id
                """
            ),
            {"name": f"Phase9 Tenant {uuid.uuid4().hex}"},
        ).fetchone()
        conn.commit()
    return row[0]


def _headers(tenant_id: int) -> dict:
    token = create_jwt(
        {
            "sub": "phase9-admin@example.com",
            "email": "phase9-admin@example.com",
            "tenant_id": tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_provider_secret_connect_list_health_and_rotate_never_returns_raw_key():
    tenant_id = _create_test_tenant()
    headers = _headers(tenant_id)
    raw_key = "sk-test-phase9-secret-value-1234567890"

    response = client.post(
        "/providers/connect",
        headers=headers,
        json={"provider": "openai", "payload": {"api_key": raw_key, "model": "gpt-4o"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["storage"] == "local_env"
    assert raw_key not in str(body)
    assert body["key_prefix"].startswith("sk-tes")

    listed = client.get("/providers/list", headers=headers)
    assert listed.status_code == 200
    listed_body = listed.json()
    assert raw_key not in str(listed_body)
    openai = next(item for item in listed_body if item["provider"] == "openai")
    assert openai["connected"] is True
    assert openai["health_status"] == "validated"
    assert openai["key_prefix"] == body["key_prefix"]

    health = client.get("/providers/openai/health", headers=headers)
    assert health.status_code == 200
    assert raw_key not in str(health.json())

    checked = client.post("/providers/openai/test", headers=headers)
    assert checked.status_code == 200
    assert checked.json()["status"] == "validated"

    rotated_key = "sk-test-phase9-rotated-secret-value-0987654321"
    rotated = client.post(
        "/providers/openai/rotate",
        headers=headers,
        json={"provider": "openai", "payload": {"api_key": rotated_key, "model": "gpt-4o"}},
    )
    assert rotated.status_code == 200
    assert rotated_key not in str(rotated.json())
    assert rotated.json()["key_prefix"] != body["key_prefix"]

    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT provider, encrypted_payload, secret_ref, secret_backend, key_prefix
                FROM tenant_credentials
                WHERE tenant_id = :tenant_id AND provider = 'openai' AND revoked_at IS NULL
                """
            ),
            {"tenant_id": tenant_id},
        ).fetchone()

    assert row is not None
    assert rotated_key not in str(dict(row._mapping))
    stored_payload = SecretManager().decrypt_from_database(row._mapping["encrypted_payload"])
    assert rotated_key not in stored_payload
    assert "secret_ref" in stored_payload


def test_provider_router_uses_secret_manager_backed_credentials():
    tenant_id = _create_test_tenant()
    headers = _headers(tenant_id)
    raw_key = "sk-test-phase9-router-secret-value-1234567890"

    response = client.post(
        "/providers/connect",
        headers=headers,
        json={"provider": "openai", "payload": {"api_key": raw_key, "model": "gpt-4o"}},
    )
    assert response.status_code == 200

    selection = ProviderRouter(tenant_id).select()
    assert selection.provider_name == "openai"
    assert selection.model == "gpt-4o"
    assert selection.source == "tenant_credential"
    assert getattr(selection.provider, "api_key") == raw_key
