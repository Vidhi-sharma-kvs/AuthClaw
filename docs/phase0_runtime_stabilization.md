# Phase 0 Runtime Stabilization

Phase 0 makes the local AuthClaw runtime repeatable without changing production gateway behavior.

## What This Adds

- `scripts/start-local.ps1` starts the FastAPI backend and Vite frontend together.
- `scripts/check-local.ps1` verifies that the backend and frontend are listening and returning HTTP 200.
- `scripts/stop-local.ps1` stops local listeners on the AuthClaw development ports.
- `AUTHCLAW_DISABLE_BACKGROUND_MONITOR=true` can disable the watched-document background scanner during local UI testing.
- `AUTHCLAW_DISABLE_REMOTE_EMBEDDINGS=true` can force deterministic local embeddings during local tests.
- Document alert emails now use the same SMTP variables as onboarding: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `SMTP_USE_TLS`.

## Why

The browser error "site can't be reached" usually means the Vite frontend is not running on port `5173`. The backend can also be healthy while the frontend is stopped. The new scripts make the local runtime explicit and check both sides.

Provider quota failures and SMTP limits are separate from local server availability. For local testing, disabling the background monitor and remote embeddings prevents unrelated provider/email limits from obscuring the core gateway, auth, and UI flows.

## Local Commands

Start:

```powershell
.\scripts\start-local.ps1
```

Check:

```powershell
.\scripts\check-local.ps1
```

Stop:

```powershell
.\scripts\stop-local.ps1
```

Expected URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Backend health: `http://127.0.0.1:8000/health/ready`

## Production Notes

Do not use the local bypass flags in production. Production should keep background monitoring enabled, SMTP configured, and provider credentials managed through the production secret path.
