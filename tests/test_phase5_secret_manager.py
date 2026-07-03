import pytest

from services.secret_manager import (
    SecretManager,
    SecretValidationError,
    StoredSecret,
    bootstrap_local_process_secrets,
    generate_fernet_key,
    generate_urlsafe_secret,
)


def clear_secret_env(monkeypatch):
    for name in [
        "AUTHCLAW_ENV",
        "AUTHCLAW_SECRET_BACKEND",
        "JWT_SECRET",
        "AUTHCLAW_JWT_SECRET",
        "AUTHCLAW_ENCRYPTION_KEY",
        "AUTHCLAW_REDACTION_SALT",
        "AWS_SECRETS_MANAGER_ENABLED",
        "AWS_REGION",
        "AWS_DEFAULT_REGION",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_local_bootstrap_creates_required_process_secrets(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_ENV", "development")

    bootstrap_local_process_secrets()
    manager = SecretManager()

    health = manager.health_check()
    assert health.healthy is True
    assert health.backend == "local_env"
    assert manager.get_required_secret("JWT_SECRET", min_length=32)
    assert manager.get_required_secret("AUTHCLAW_REDACTION_SALT", min_length=32)


def test_production_rejects_local_secret_backend(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_ENV", "production")
    monkeypatch.setenv("AUTHCLAW_SECRET_BACKEND", "local_env")
    monkeypatch.setenv("JWT_SECRET", generate_urlsafe_secret())
    monkeypatch.setenv("AUTHCLAW_ENCRYPTION_KEY", generate_fernet_key())
    monkeypatch.setenv("AUTHCLAW_REDACTION_SALT", generate_urlsafe_secret())

    with pytest.raises(SecretValidationError):
        SecretManager().validate_startup(production=True)


def test_encrypt_decrypt_roundtrip_uses_secret_manager(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_SECRET_BACKEND", "local_env")
    monkeypatch.setenv("JWT_SECRET", generate_urlsafe_secret())
    monkeypatch.setenv("AUTHCLAW_ENCRYPTION_KEY", generate_fernet_key())
    monkeypatch.setenv("AUTHCLAW_REDACTION_SALT", generate_urlsafe_secret())

    manager = SecretManager()
    encrypted = manager.encrypt_for_database("sensitive-provider-key")

    assert "sensitive-provider-key" not in encrypted
    assert manager.decrypt_from_database(encrypted) == "sensitive-provider-key"


def test_redaction_fingerprint_requires_secret_salt(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_SECRET_BACKEND", "local_env")
    monkeypatch.setenv("JWT_SECRET", generate_urlsafe_secret())
    monkeypatch.setenv("AUTHCLAW_ENCRYPTION_KEY", generate_fernet_key())
    monkeypatch.setenv("AUTHCLAW_REDACTION_SALT", "x" * 48)

    manager = SecretManager()
    assert manager.fingerprint("vidhi@example.com", purpose="redaction") == manager.fingerprint(
        "vidhi@example.com", purpose="redaction"
    )
    assert manager.fingerprint("vidhi@example.com", purpose="redaction") != manager.fingerprint(
        "vidhi@example.com", purpose="other"
    )


def test_stored_secret_repr_does_not_expose_value():
    stored = StoredSecret(name="authclaw/test", backend="local_env", version_id="v1", value="raw-secret")
    assert "raw-secret" not in repr(stored)


def test_aws_secrets_manager_backend_get_put_delete_and_health(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_SECRET_BACKEND", "aws_secrets_manager")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    class FakeAwsSecretsClient:
        class exceptions:
            class ResourceNotFoundException(Exception):
                pass

        def __init__(self):
            self.secrets = {}

        def get_secret_value(self, SecretId):
            if SecretId not in self.secrets:
                raise self.exceptions.ResourceNotFoundException()
            return {"SecretString": self.secrets[SecretId]}

        def put_secret_value(self, SecretId, SecretString):
            if SecretId not in self.secrets:
                raise self.exceptions.ResourceNotFoundException()
            self.secrets[SecretId] = SecretString
            return {"VersionId": "aws-v2"}

        def create_secret(self, Name, SecretString):
            self.secrets[Name] = SecretString
            return {"VersionId": "aws-v1"}

        def delete_secret(self, SecretId, ForceDeleteWithoutRecovery):
            self.secrets.pop(SecretId, None)

    fake_client = FakeAwsSecretsClient()

    import boto3

    monkeypatch.setattr(boto3, "client", lambda service_name, region_name: fake_client)

    manager = SecretManager()
    stored = manager.put_secret("authclaw/test/aws", "managed-secret-value")

    assert stored.backend == "aws_secrets_manager"
    assert manager.health_check().healthy is True
    assert manager.get_secret("authclaw/test/aws") == "managed-secret-value"

    manager.delete_secret("authclaw/test/aws")

    with pytest.raises(Exception):
        manager.get_secret("authclaw/test/aws")


def test_hashicorp_vault_backend_get_put_and_health(monkeypatch):
    clear_secret_env(monkeypatch)
    monkeypatch.setenv("AUTHCLAW_SECRET_BACKEND", "hashicorp_vault")
    monkeypatch.setenv("VAULT_ADDR", "http://vault.example.test:8200/v1")
    monkeypatch.setenv("VAULT_TOKEN", "vault-token")
    monkeypatch.setenv("VAULT_KV_MOUNT", "secret")

    calls = []
    vault_values = {}

    class FakeResponse:
        def __init__(self, status_code=200, payload=None, text="{}"):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

    def fake_request(method, url, headers=None, json=None, timeout=None):
        calls.append((method, url, headers, json, timeout))
        if url.endswith("/v1/sys/health"):
            return FakeResponse(text="")
        if method == "POST":
            vault_values[url] = json["data"]["value"]
            return FakeResponse()
        if method == "GET":
            return FakeResponse(payload={"data": {"data": {"value": vault_values[url]}}})
        raise AssertionError(f"unexpected method {method}")

    import requests

    monkeypatch.setattr(requests, "request", fake_request)

    manager = SecretManager()
    stored = manager.put_secret("authclaw/test/vault", "vault-secret-value")

    assert stored.backend == "hashicorp_vault"
    assert manager.health_check().healthy is True
    assert manager.get_secret("authclaw/test/vault") == "vault-secret-value"
    assert all(call[2]["X-Vault-Token"] == "vault-token" for call in calls)
    assert any(call[1] == "http://vault.example.test:8200/v1/secret/data/authclaw/test/vault" for call in calls)
