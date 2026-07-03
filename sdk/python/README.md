# AuthClaw Python SDK

This directory is reserved for the Python client SDK package.

Until the SDK is packaged, customer applications can call the gateway directly:

```python
import requests

response = requests.post(
    "https://YOUR_AUTHCLAW_HOST/api/gateway/chat",
    headers={
        "Authorization": "Bearer YOUR_AUTHCLAW_API_KEY",
        "Content-Type": "application/json",
    },
    json={
        "session_id": "customer-session-001",
        "message": "Hello through AuthClaw governance.",
    },
    timeout=60,
)

print(response.json())
```

Never expose AuthClaw API keys in browser code. Send gateway requests from your
backend service.
