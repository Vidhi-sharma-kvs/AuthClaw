# AuthClaw Testing Guide

Recommended code validation:

```bash
python -m pytest tests/test_production_completion_readiness.py
python -m pytest
cd gateway-go && go test ./...
cd frontend && npm run build && npm run lint
python scripts/terraform_config_validate.py --fail-on-missing
python scripts/dr_readiness_validate.py --fail-on-code-gaps
```

Playwright real-app E2E:

```bash
cd frontend
AUTHCLAW_E2E_BASE_URL=http://127.0.0.1:5175 \
AUTHCLAW_E2E_EMAIL=admin@example.com \
AUTHCLAW_E2E_PASSWORD='real-password' \
npm run e2e
```

If the account requires MFA, also set `AUTHCLAW_E2E_OTP_CODE`. Registration E2E is disabled by default; enable only when you intend to create a real onboarding record:

```bash
AUTHCLAW_E2E_ENABLE_ONBOARDING=1 npm run e2e
```

The Playwright suite uses real frontend/backend APIs and does not mock network responses.
