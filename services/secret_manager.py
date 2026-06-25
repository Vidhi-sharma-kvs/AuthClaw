import json
import os
from typing import Optional


class SecretManagerError(RuntimeError):
    pass


class SecretManager:
    def __init__(self):
        self.aws_enabled = os.getenv("AWS_SECRETS_MANAGER_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.region_name = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

    def get_secret(self, name: str) -> Optional[str]:
        if self.aws_enabled:
            return self._get_aws_secret(name)
        return os.getenv(name)

    def put_secret(self, name: str, value: str) -> None:
        if not self.aws_enabled:
            raise SecretManagerError("Secret rotation requires AWS_SECRETS_MANAGER_ENABLED=true.")
        self._put_aws_secret(name, value)

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

    def _put_aws_secret(self, name: str, value: str) -> None:
        client = self._client()
        try:
            client.put_secret_value(SecretId=name, SecretString=value)
        except Exception as exc:
            raise SecretManagerError(f"Unable to rotate AWS secret {name}: {exc}") from exc
