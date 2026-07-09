# AuthClaw Python SDK

Installable Python client for AuthClaw gateway, provider, approval, audit,
remediation, and Trust Center APIs.

```python
from authclaw_client import AuthClawClient, AuthClawRateLimitError

client = AuthClawClient(
    "https://app.authclaw.example.com",
    "YOUR_AUTHCLAW_API_KEY",
    timeout=30,
    max_retries=3,
)

response = client.gateway_chat(
    "Hello through AuthClaw governance.",
    session_id="customer-session-001",
)
print(response.message)

for event in client.stream_chat_completion([
    {"role": "user", "content": "Summarize this through AuthClaw."}
]):
    print(event)

try:
    provider = client.test_provider("openai")
    print(provider.status)
except AuthClawRateLimitError:
    print("Try again after the configured tenant rate-limit window.")
```

Never expose AuthClaw API keys in browser code. Send gateway requests from your
backend service.

## Capabilities

- Retries with exponential backoff for transient `408/425/429/5xx` responses.
- Per-request timeout.
- Typed wrappers for common response shapes.
- Streaming Server-Sent Events support for `/v1/chat/completions`.
- Structured exceptions for authentication, rate limiting, server errors, and
  timeouts.
- Helpers for provider credentials, API keys, approvals with MFA, remediation,
  audit verification, signed export verification, policies, and public Trust
  Center state.
