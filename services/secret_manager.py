import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet


class SecretManagerError(RuntimeError):
    pass


@dataclass
class StoredSecret:
    name: str
    value: str
    backend: str
    version_id: Optional[str] = None


def normalize_provider(provider: str) -> str:
    normalized = (provider or "").lower().replace(" ", "_")
    if normalized in {"google_gemini", "gemini"}:
        return "gemini"
    if normalized in {"azure", "azure_openai"}:
        return "azure_openai"
    if normalized in {"anthropic", "claude"}:
        return "anthropic"
    return normalized


def secret_name_for_provider(tenant_id: int, provider: str) -> str:
    return f"authclaw/tenants/{tenant_id}/providers/{normalize_provider(provider)}"


def credential_fingerprint(payload: Dict[str, Any]) -> str:
    api_key = str(payload.get("api_key") or "")
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16] if api_key else ""


def credential_prefix(payload: Dict[str, Any]) -> str:
    api_key = str(payload.get("api_key") or "")
    if not api_key:
        return ""
    return f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 12 else f"{api_key[:3]}..."


class SecretManager:
    def __init__(self):
        self.aws_enabled = os.getenv("AWS_SECRETS_MANAGER_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.region_name = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
        self.encryption_key = os.getenv("AUTHCLAW_ENCRYPTION_KEY", "uK2zL_s-Upxl3k88J9o0nK4qR2_l8U90jK1l4u89mKo=")

    @property
    def backend(self) -> str:
        return "aws_secrets_manager" if self.aws_enabled else "database_fernet"

    def get_secret(self, name: str) -> Optional[str]:
        if self.aws_enabled:
            return self._get_aws_secret(name)
        return os.getenv(name)

    def put_secret(self, name: str, value: str) -> StoredSecret:
        if self.aws_enabled:
            version_id = self._put_aws_secret(name, value)
            return StoredSecret(name=name, value=value, backend=self.backend, version_id=version_id)
        return StoredSecret(name=name, value=value, backend=self.backend, version_id=None)

    def delete_secret(self, name: str) -> None:
        if self.aws_enabled:
            self._delete_aws_secret(name)

    def encrypt_for_database(self, value: str) -> str:
        return Fernet(self.encryption_key.encode("utf-8")).encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_from_database(self, encrypted_value: str) -> str:
        return Fernet(self.encryption_key.encode("utf-8")).decrypt(encrypted_value.encode("utf-8")).decode("utf-8")

    def store_provider_payload(self, tenant_id: int, provider: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized_provider = normalize_provider(provider)
        secret_name = secret_name_for_provider(tenant_id, normalized_provider)
        secret_value = json.dumps(payload)
        stored = self.put_secret(secret_name, secret_value)
        database_payload = (
            json.dumps({"provider": normalized_provider, "secret_ref": stored.name})
            if self.aws_enabled
            else secret_value
        )
        encrypted_payload = self.encrypt_for_database(database_payload)
        now = datetime.now(timezone.utc).isoformat()
        return {
            "provider": normalized_provider,
            "secret_ref": stored.name,
            "secret_backend": stored.backend,
            "secret_version": stored.version_id,
            "encrypted_payload": encrypted_payload,
            "key_fingerprint": credential_fingerprint(payload),
            "key_prefix": credential_prefix(payload),
            "rotated_at": now,
        }

    def resolve_provider_payload(self, credential_row: Dict[str, Any]) -> Dict[str, Any]:
        backend = credential_row.get("secret_backend") or "database_fernet"
        secret_ref = credential_row.get("secret_ref")
        if backend == "aws_secrets_manager" and secret_ref:
            secret_value = self._get_aws_secret(secret_ref)
            if secret_value:
                return json.loads(secret_value)

        encrypted_payload = credential_row.get("encrypted_payload")
        if not encrypted_payload:
            raise SecretManagerError("Provider credential payload is missing.")
        return json.loads(self.decrypt_from_database(encrypted_payload))

    def get_json_secret(self, name: str) -> Optional[dict]:
        value = self.get_secret(name)
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise SecretManagerError(f"Secret {name} is not valid JSON.") from exc

    def _client(self):
        try:
            import boto3
        except ImportError as exc:
            raise SecretManagerError("boto3 is required when AWS Secrets Manager is enabled.") from exc
        if not self.region_name:
            raise SecretManagerError("AWS_REGION or AWS_DEFAULT_REGION is required for AWS Secrets Manager.")
        return boto3.client("secretsmanager", region_name=self.region_name)

    def _get_aws_secret(self, name: str) -> Optional[str]:
        client = self._client()
        try:
            response = client.get_secret_value(SecretId=name)
        except Exception as exc:
            raise SecretManagerError(f"Unable to read AWS secret {name}: {exc}") from exc
        return response.get("SecretString")

    def _put_aws_secret(self, name: str, value: str) -> Optional[str]:
        client = self._client()
        try:
            try:
                response = client.put_secret_value(SecretId=name, SecretString=value)
            except client.exceptions.ResourceNotFoundException:
                response = client.create_secret(Name=name, SecretString=value)
            return response.get("VersionId")
        except Exception as exc:
            raise SecretManagerError(f"Unable to store AWS secret {name}: {exc}") from exc

    def _delete_aws_secret(self, name: str) -> None:
        client = self._client()
        try:
            client.delete_secret(SecretId=name, ForceDeleteWithoutRecovery=True)
        except client.exceptions.ResourceNotFoundException:
            return
        except Exception as exc:
            raise SecretManagerError(f"Unable to delete AWS secret {name}: {exc}") from exc
