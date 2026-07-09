# Phase 11 SDK, Developer Experience, And Documentation

## SDK

The Python SDK is installable from `sdk/python` and keeps the stable import path:

```bash
pip install ./sdk/python
```

It provides:

- Request retries and exponential backoff for transient gateway/API failures.
- Per-request timeouts.
- Typed response wrappers and structured exception classes.
- Streaming support for OpenAI-compatible chat completions.
- Helpers for providers, API keys, approvals, remediation, audit verification, signed export verification, policies, and Trust Center state.

## OpenAPI

The backend exposes `/openapi.json`. Public API documentation should be generated from that endpoint after each production deployment and compared against the SDK methods before release.

Local generation:

```bash
curl http://127.0.0.1:8000/openapi.json > openapi.json
```

## Production Customer Onboarding

1. Configure tenant onboarding, verified domain, and IdP/OIDC if required.
2. Connect provider credentials from the console or SDK.
3. Create tenant API keys for backend services only.
4. Validate `/health/ready`, `/providers/{provider}/test`, `/audit/verify`, and `/trust/public`.
5. Install the SDK into a server-side service and route gateway requests through AuthClaw.
