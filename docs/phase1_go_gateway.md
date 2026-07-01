# Phase 1 - Dedicated Go Gateway

AuthClaw now has a mandatory Go gateway substrate in `gateway-go/`.

Runtime topology:

```text
Browser / Customer App
  -> AuthClaw Go Gateway :9000
  -> Python Governance Backend :8000
  -> Security Agent / Policy Agent / Provider Router / Audit Agent
```

The Go gateway is intentionally thin in Phase 1. It owns the network boundary,
health checks, CORS, request logging, path normalization, and reverse-proxy
handoff to the existing Python governance backend. Business logic remains in
the current Python services.

Mandatory local ports:

- Frontend: `http://127.0.0.1:5173`
- Go Gateway: `http://127.0.0.1:9000`
- Python API: `http://127.0.0.1:8000`

Gateway entry points supported by Go:

- `POST /gateway/chat`
- `POST /api/gateway/chat`
- `POST /chat`
- `POST /v1/chat/completions`
- `POST /gateway/documents/*`
- `POST /api/gateway/documents/*`

The `/api/*` prefix is normalized before forwarding to Python. This allows a
single-domain deployment where the frontend can call `/api/...`, while direct
customer integrations can call the Go gateway host directly.

Local startup:

```powershell
.\scripts\start-local.ps1
```

Go 1.22+ is mandatory. If `go` is missing, the startup script fails with a
clear installation message instead of silently bypassing the gateway.
