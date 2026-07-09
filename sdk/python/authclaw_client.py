"""Production Python SDK for AuthClaw.

The SDK intentionally uses the Python standard library so customers can install
it in controlled enterprise environments without pulling an HTTP stack that may
conflict with their application.
"""

import json
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional


JsonDict = Dict[str, Any]


class AuthClawError(Exception):
    """Base SDK error."""


class AuthClawAPIError(AuthClawError):
    """Backend returned a non-success response."""

    def __init__(self, message: str, status_code: int, payload: Optional[JsonDict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class AuthClawAuthenticationError(AuthClawAPIError):
    """Authentication or authorization failed."""


class AuthClawRateLimitError(AuthClawAPIError):
    """AuthClaw rate limit rejected the request."""


class AuthClawServerError(AuthClawAPIError):
    """AuthClaw returned a transient server-side error."""


class AuthClawTimeoutError(AuthClawError):
    """The request timed out after all retry attempts."""


@dataclass(frozen=True)
class SDKResponse:
    data: JsonDict
    status_code: int
    headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayChatResponse:
    message: str
    raw: JsonDict


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    status: str
    raw: JsonDict


@dataclass(frozen=True)
class Approval:
    approval_id: str
    status: str
    raw: JsonDict


@dataclass(frozen=True)
class RemediationFinding:
    finding_id: str
    provider: str
    severity: str
    raw: JsonDict


class AuthClawClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.25,
        user_agent: str = "authclaw-python-sdk/1.0",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.retry_backoff = max(0.0, retry_backoff)
        self.user_agent = user_agent

    def _headers(self, extra: Optional[Mapping[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": self.user_agent,
        }
        headers.update(dict(extra or {}))
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[JsonDict] = None,
        headers: Optional[Mapping[str, str]] = None,
        raw_body: Optional[bytes] = None,
    ) -> SDKResponse:
        body = raw_body
        request_headers = self._headers(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=request_headers,
            method=method.upper(),
        )
        last_error: Optional[BaseException] = None
        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
                    response_body = response.read().decode("utf-8")
                    data = json.loads(response_body) if response_body else {}
                    return SDKResponse(data=data, status_code=response.status, headers=dict(response.headers))
            except urllib.error.HTTPError as exc:
                payload_data = self._decode_error_payload(exc)
                if exc.code in {408, 425, 429, 500, 502, 503, 504} and attempt < self.max_retries:
                    self._sleep_before_retry(attempt, exc.headers.get("Retry-After"))
                    continue
                raise self._map_api_error(exc.code, payload_data) from exc
            except TimeoutError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise AuthClawTimeoutError("AuthClaw request timed out") from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    self._sleep_before_retry(attempt)
                    continue
                raise AuthClawError(f"AuthClaw request failed: {exc.reason}") from exc
        raise AuthClawError(f"AuthClaw request failed: {last_error}")

    @staticmethod
    def _decode_error_payload(exc: urllib.error.HTTPError) -> JsonDict:
        try:
            raw = exc.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}

    def _sleep_before_retry(self, attempt: int, retry_after: Optional[str] = None) -> None:
        if retry_after:
            try:
                time.sleep(float(retry_after))
                return
            except ValueError:
                pass
        time.sleep(self.retry_backoff * (2**attempt))

    @staticmethod
    def _map_api_error(status_code: int, payload: JsonDict) -> AuthClawAPIError:
        message = str(payload.get("detail") or payload.get("error") or f"AuthClaw API error {status_code}")
        if status_code in {401, 403}:
            return AuthClawAuthenticationError(message, status_code, payload)
        if status_code == 429:
            return AuthClawRateLimitError(message, status_code, payload)
        if status_code >= 500:
            return AuthClawServerError(message, status_code, payload)
        return AuthClawAPIError(message, status_code, payload)

    def get(self, path: str) -> JsonDict:
        return self._request("GET", path).data

    def post(self, path: str, payload: Optional[JsonDict] = None) -> JsonDict:
        return self._request("POST", path, payload or {}).data

    def delete(self, path: str) -> JsonDict:
        return self._request("DELETE", path).data

    def gateway_chat(self, message: str, session_id: Optional[str] = None, **kwargs: Any) -> GatewayChatResponse:
        payload: JsonDict = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        payload.update(kwargs)
        data = self.post("/gateway/chat", payload)
        return GatewayChatResponse(message=str(data.get("response") or data.get("message") or ""), raw=data)

    def chat_completions(self, messages: Iterable[Mapping[str, str]], model: str = "authclaw-gateway", **kwargs: Any) -> JsonDict:
        payload: JsonDict = {"model": model, "messages": list(messages)}
        payload.update(kwargs)
        return self.post("/v1/chat/completions", payload)

    def stream_chat_completion(
        self,
        messages: Iterable[Mapping[str, str]],
        model: str = "authclaw-gateway",
        **kwargs: Any,
    ) -> Iterator[JsonDict]:
        payload: JsonDict = {"model": model, "messages": list(messages), "stream": True}
        payload.update(kwargs)
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers({"Accept": "text/event-stream", "Content-Type": "application/json"}),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                yield json.loads(data)

    def redact_document(self, filename: str, content: bytes, content_type: str = "text/plain") -> JsonDict:
        boundary = f"----authclaw-{uuid.uuid4().hex}"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"),
                f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
                content if isinstance(content, bytes) else str(content).encode("utf-8"),
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            ]
        )
        response = self._request(
            "POST",
            "/gateway/documents/redact",
            raw_body=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        return response.data

    def list_providers(self) -> List[ProviderStatus]:
        data = self.get("/providers/list")
        items = data if isinstance(data, list) else data.get("providers", [])
        return [ProviderStatus(provider=str(item.get("provider") or item.get("id") or ""), status=str(item.get("status") or "unknown"), raw=item) for item in items]

    def connect_provider(self, provider: str, credentials: Mapping[str, Any], **metadata: Any) -> JsonDict:
        payload = {"provider": provider, "credentials": dict(credentials)}
        payload.update(metadata)
        return self.post("/providers/connect", payload)

    def test_provider(self, provider: str) -> ProviderStatus:
        data = self.post(f"/providers/{provider}/test")
        return ProviderStatus(provider=provider, status=str(data.get("status") or "unknown"), raw=data)

    def rotate_provider(self, provider: str, credentials: Mapping[str, Any]) -> JsonDict:
        return self.post(f"/providers/{provider}/rotate", {"credentials": dict(credentials)})

    def delete_provider(self, provider: str) -> JsonDict:
        return self.delete(f"/providers/{provider}")

    def provider_health(self, provider: str) -> ProviderStatus:
        data = self.get(f"/providers/{provider}/health")
        return ProviderStatus(provider=provider, status=str(data.get("status") or "unknown"), raw=data)

    def list_approvals(self) -> List[Approval]:
        data = self.get("/approvals")
        items = data if isinstance(data, list) else data.get("approvals", [])
        return [Approval(approval_id=str(item.get("approval_id") or item.get("id") or ""), status=str(item.get("status") or ""), raw=item) for item in items]

    def approve(self, approval_id: str, mfa_code: str, comment: str = "") -> Approval:
        data = self.post(f"/approve/{approval_id}", {"mfa_code": mfa_code, "comment": comment})
        return Approval(approval_id=approval_id, status=str(data.get("status") or "approved"), raw=data)

    def execute_approval(self, approval_id: str, mfa_code: str, comment: str = "") -> Approval:
        data = self.post(f"/execute/{approval_id}", {"mfa_code": mfa_code, "comment": comment})
        return Approval(approval_id=approval_id, status=str(data.get("status") or "executed"), raw=data)

    def reject(self, approval_id: str, comment: str = "") -> Approval:
        data = self.post(f"/reject/{approval_id}", {"comment": comment})
        return Approval(approval_id=approval_id, status=str(data.get("status") or "rejected"), raw=data)

    def approval_history(self, approval_id: str) -> JsonDict:
        return self.get(f"/approvals/{approval_id}/history")

    def generate_api_key(self, name: str, **kwargs: Any) -> JsonDict:
        payload = {"name": name}
        payload.update(kwargs)
        return self.post("/keys/generate", payload)

    def list_api_keys(self) -> JsonDict:
        return self.get("/keys/list")

    def rotate_api_key(self, key_id: str) -> JsonDict:
        return self.post(f"/keys/{key_id}/rotate")

    def delete_api_key(self, key_id: str) -> JsonDict:
        return self.delete(f"/keys/{key_id}")

    def list_remediation_connectors(self) -> JsonDict:
        return self.get("/remediation/connectors")

    def create_remediation_connector(self, provider: str, config: Mapping[str, Any]) -> JsonDict:
        return self.post("/remediation/connectors", {"provider": provider, "config": dict(config)})

    def test_remediation_connector(self, connector_id: str) -> JsonDict:
        return self.post(f"/remediation/connectors/{connector_id}/test")

    def launch_remediation_scan(self, connector_id: str, mode: str = "read_only") -> JsonDict:
        return self.post("/remediation/scans", {"connector_id": connector_id, "mode": mode})

    def list_remediation_findings(self) -> List[RemediationFinding]:
        data = self.get("/remediation/findings")
        items = data if isinstance(data, list) else data.get("findings", [])
        return [
            RemediationFinding(
                finding_id=str(item.get("finding_id") or item.get("id") or ""),
                provider=str(item.get("provider") or ""),
                severity=str(item.get("severity") or "unknown"),
                raw=item,
            )
            for item in items
        ]

    def create_remediation_plan(self, finding_id: str) -> JsonDict:
        return self.post(f"/remediation/findings/{finding_id}/plan")

    def request_remediation_approval(self, plan_id: str, comment: str = "") -> JsonDict:
        return self.post(f"/remediation/plans/{plan_id}/approval", {"comment": comment})

    def get_remediation_worker(self, worker_id: str) -> JsonDict:
        return self.get(f"/remediation/workers/{worker_id}")

    def audit_verify(self) -> JsonDict:
        return self.get("/audit/verify")

    def audit_hash_chain(self) -> JsonDict:
        return self.get("/audit/hash-chain")

    def export_auditor_package(self, **params: Any) -> JsonDict:
        query = ""
        if params:
            encoded = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
            query = f"?{encoded}" if encoded else ""
        return self.get(f"/auditor/package/export{query}")

    def verify_export(self, package: Mapping[str, Any]) -> JsonDict:
        return self.post("/audit/export/verify", dict(package))

    def get_public_trust_state(self) -> JsonDict:
        return self.get("/trust/public")

    def list_policies(self) -> JsonDict:
        return self.get("/policies/list")

    def simulate_policy(self, policy_id: str, input_payload: Mapping[str, Any]) -> JsonDict:
        return self.post(f"/policies/{policy_id}/simulate", dict(input_payload))
