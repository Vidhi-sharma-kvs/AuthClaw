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
