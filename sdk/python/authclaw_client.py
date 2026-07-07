import json
import uuid
import urllib.request
from typing import Dict, Iterable, Optional


class AuthClawClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        headers.update(extra or {})
        return headers

    def _post_json(self, path: str, payload: Dict) -> Dict:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8") or "{}")

    def gateway_chat(self, message: str, session_id: Optional[str] = None, **kwargs) -> Dict:
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        payload.update(kwargs)
        return self._post_json("/gateway/chat", payload)

    def stream_chat_completion(self, messages: Iterable[Dict[str, str]], model: str = "authclaw-gateway"):
        payload = {"model": model, "messages": list(messages), "stream": True}
        request = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers({"Accept": "text/event-stream"}),
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

    def redact_document(self, filename: str, content: bytes, content_type: str = "text/plain") -> Dict:
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
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        request = urllib.request.Request(
            f"{self.base_url}/gateway/documents/redact",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8") or "{}")
