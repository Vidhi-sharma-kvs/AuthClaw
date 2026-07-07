# AuthClaw Python SDK

This directory contains a lightweight Python client wrapper for backend services.

```python
from authclaw_client import AuthClawClient

client = AuthClawClient("https://YOUR_AUTHCLAW_HOST/api", "YOUR_AUTHCLAW_API_KEY")

response = client.gateway_chat(
    "Hello through AuthClaw governance.",
    session_id="customer-session-001",
)

for event in client.stream_chat_completion([
    {"role": "user", "content": "Summarize this through AuthClaw."}
]):
    print(event)
```

Never expose AuthClaw API keys in browser code. Send gateway requests from your
backend service.
