# AuthClaw Applications

This directory is the product-facing application index for monorepo tooling.
Runtime source stays in the existing stable paths so imports, Dockerfiles, CI,
deployment scripts, and local startup behavior remain backward compatible. The
folders below now include runnable wrappers or command delegates for tools that
expect `apps/*` entrypoints.

| App | Runtime path | Purpose |
| --- | --- | --- |
| Backend API | `../main.py`, `../routers/`, `../services/` | FastAPI governance backend, admin APIs, policy, audit, approvals, documents |
| Web Console | `../frontend/` | React/Vite customer and administration console |
| Go Gateway | `../gateway-go/` | Mandatory gateway substrate and streaming redaction runtime |

## Commands

```bash
python -m uvicorn apps.backend.main:app --host 127.0.0.1 --port 8000
npm --prefix apps/web run build
go test ./gateway-go/...
```
