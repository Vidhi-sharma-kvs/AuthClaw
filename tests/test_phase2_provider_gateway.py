import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import app, create_jwt
from providers.anthropic_provider import AnthropicProvider
from providers.azure_openai_provider import AzureOpenAIProvider
from providers.cohere_provider import CohereProvider
from providers.openai_provider import OpenAIProvider


client = TestClient(app)


class _Response:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _create_tenant() -> int:
    with engine.connect() as conn:
        tenant_id = conn.execute(
            text(
                """
                INSERT INTO tenants (name, status, email_verified, domain_verified)
                VALUES (:name, 'active', TRUE, TRUE)
                RETURNING id
                """
            ),
            {"name": f"Phase2 Provider Tenant {uuid.uuid4().hex}"},
        ).scalar()
        conn.commit()
    return tenant_id


def _headers(tenant_id: int) -> dict:
    token = create_jwt(
        {
            "sub": "phase2-admin@example.com",
            "email": "phase2-admin@example.com",
            "tenant_id": tenant_id,
            "role": "Super Admin",
            "permissions": "all_access",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _payload_for(provider: str, api_key: str) -> dict:
    if provider == "azure_openai":
        return {
            "api_key": api_key,
            "api_base": "https://resource.openai.azure.com",
            "api_version": "2024-02-15-preview",
            "deployment": "gpt-4o-prod",
            "model": "gpt-4o-prod",
        }
    defaults = {
        "openai": {"api_key": api_key, "model": "gpt-4o"},
        "anthropic": {"api_key": api_key, "model": "claude-3-5-sonnet-20241022"},
        "cohere": {"api_key": api_key, "model": "command-r-plus"},
    }
    return defaults[provider]


def test_provider_credential_lifecycle_for_all_srs_providers():
    tenant_id = _create_tenant()
    headers = _headers(tenant_id)
    providers = ["openai", "anthropic", "cohere", "azure_openai"]

    for provider in providers:
        raw_key = f"{provider}-phase2-secret-key-1234567890"
        connect = client.post(
            "/providers/connect",
            headers=headers,
            json={"provider": provider, "payload": _payload_for(provider, raw_key)},
        )
        assert connect.status_code == 200, connect.text
        assert connect.json()["provider"] == provider
        assert raw_key not in str(connect.json())

        health = client.get(f"/providers/{provider}/health", headers=headers)
        assert health.status_code == 200
        assert health.json()["health_status"] == "validated"
        assert raw_key not in str(health.json())

        test = client.post(f"/providers/{provider}/test", headers=headers)
        assert test.status_code == 200
        assert test.json()["status"] == "validated"

        rotated_key = f"{provider}-phase2-rotated-secret-key-1234567890"
        rotate = client.post(
            f"/providers/{provider}/rotate",
            headers=headers,
            json={"provider": provider, "payload": _payload_for(provider, rotated_key)},
        )
        assert rotate.status_code == 200
        assert rotated_key not in str(rotate.json())

        delete = client.delete(f"/providers/{provider}", headers=headers)
        assert delete.status_code == 200


def test_provider_connect_accepts_legacy_top_level_payload_for_frontend_compatibility():
    tenant_id = _create_tenant()
    headers = _headers(tenant_id)
    response = client.post(
        "/providers/connect",
        headers=headers,
        json={
            "provider": "azure_openai",
            "api_key": "azure-top-level-secret-1234567890",
            "azure_endpoint": "https://resource.openai.azure.com",
            "azure_api_version": "2024-02-15-preview",
            "deployment": "gpt-4o-prod",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "azure_openai"


def test_native_provider_payloads_are_provider_compatible(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append({"url": url, **kwargs})
        if "/v1/messages" in url:
            return _Response({"content": [{"type": "text", "text": "anthropic ok"}]})
        if "/v2/chat" in url:
            return _Response({"message": {"content": [{"type": "text", "text": "cohere ok"}]}})
        return _Response({"choices": [{"message": {"content": "openai ok"}}]})

    monkeypatch.setattr("requests.post", fake_post)

    assert OpenAIProvider(api_key="sk-test").generate("hello") == "openai ok"
    assert AnthropicProvider(api_key="sk-ant-test").generate("hello") == "anthropic ok"
    assert CohereProvider(api_key="cohere-test-key-1234567890").generate("hello") == "cohere ok"
    assert AzureOpenAIProvider(
        api_key="azure-test-key",
        deployment="gpt-4o-prod",
        api_url="https://resource.openai.azure.com",
        api_version="2024-02-15-preview",
    ).generate("hello") == "openai ok"

    openai_call, anthropic_call, cohere_call, azure_call = calls
    assert openai_call["url"] == "https://api.openai.com/v1/chat/completions"
    assert openai_call["json"]["messages"][-1] == {"role": "user", "content": "hello"}
    assert anthropic_call["url"] == "https://api.anthropic.com/v1/messages"
    assert anthropic_call["headers"]["anthropic-version"] == "2023-06-01"
    assert cohere_call["url"] == "https://api.cohere.com/v2/chat"
    assert cohere_call["json"]["messages"][-1] == {"role": "user", "content": "hello"}
    assert azure_call["url"] == "https://resource.openai.azure.com/openai/deployments/gpt-4o-prod/chat/completions"
    assert azure_call["params"] == {"api-version": "2024-02-15-preview"}
    assert azure_call["headers"]["api-key"] == "azure-test-key"
