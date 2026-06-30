# Phase 2 Gateway Verification

Phase 2 keeps runtime behavior unchanged and makes the local verification path deterministic.

## What Changed

- Tenant users who successfully sign in now land on `/chat`, the gateway-first workspace, instead of `/dashboard`.
- Gateway route tests use a pytest-only provider fixture so `/gateway/chat`, `/chat`, and `/v1/chat/completions` can verify request tracking, audit writes, and trace writes without calling an external LLM.

## Why

Production gateway requests must use tenant-owned provider credentials or configured environment secrets. Tests should not depend on a live Gemini, OpenAI, Anthropic, or Azure account because that makes CI flaky and can consume quota. The pytest fixture verifies AuthClaw's governance lifecycle while keeping real runtime fail-closed behavior intact.

## Runtime Safety

The deterministic provider exists only in `test_gateway_chat.py`. It is not imported by `ProviderRouter`, `GatewayService`, `main.py`, or frontend code. Production still follows:

```text
Tenant/API key
-> GatewayService
-> LangGraph
-> ProviderRouter
-> tenant_credentials or environment provider secret
-> LLM provider
-> response inspection
-> audit and registrar
```

If no provider is configured in runtime, the gateway still fails closed with `provider_unavailable`.

## Verification

```powershell
cd frontend
npm run build

cd ..
.\venv\Scripts\python.exe -m pytest test_auth_backend.py test_gateway_chat.py
```

