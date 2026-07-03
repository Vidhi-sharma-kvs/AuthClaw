# AuthClaw Applications

This directory is the product-facing application index for GitHub readers.
Runtime source stays in the existing stable paths so imports, Dockerfiles, CI,
deployment scripts, and local startup behavior remain backward compatible.

| App | Runtime path | Purpose |
| --- | --- | --- |
| Backend API | `../main.py`, `../routers/`, `../services/` | FastAPI governance backend, admin APIs, policy, audit, approvals, documents |
| Web Console | `../frontend/` | React/Vite customer and administration console |
| Go Gateway | `../gateway-go/` | Mandatory gateway substrate and streaming redaction runtime |
