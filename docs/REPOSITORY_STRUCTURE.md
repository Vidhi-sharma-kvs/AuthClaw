# Repository Structure

This repository is organized around the gateway-first AuthClaw architecture.

## GitHub Presentation

These directories provide a clean GitHub landing structure without moving
runtime code or changing application behavior.

| Path | Responsibility |
| --- | --- |
| `apps/` | Product-facing index for backend, web console, and Go gateway |
| `infrastructure/` | Deployment and cloud infrastructure index pointing to existing deployable assets |
| `sdk/python/` | Python SDK placeholder and customer integration example |

## Runtime

| Path | Responsibility |
| --- | --- |
| `gateway-go/` | Mandatory LLM traffic entry point, proxy behavior, streaming redaction, gateway health |
| `main.py` | FastAPI application composition and legacy-compatible backend entry point |
| `routers/` | Route-level API organization for auth, chat, gateway, approvals, policy, settings, and admin APIs |
| `services/` | Business logic for authentication, policy evaluation, provider routing, audit, metrics, approvals, and secrets |
| `providers/` | LLM provider adapters and routing helpers |
| `nodes/`, `graphs/` | Agent and graph orchestration pieces |

## Data And Governance

| Path | Responsibility |
| --- | --- |
| `database/` | Database connections, schema setup, migrations, tenant/RLS helpers |
| `document_processing/` | Document extraction, OCR, findings, redaction, persistence, and audit integration |
| `rag/` | Retrieval and knowledge pipeline components |
| `policies.yaml` | Local policy configuration seed/input |

## Frontend

| Path | Responsibility |
| --- | --- |
| `frontend/src/` | React dashboard and administration experience |
| `frontend/Dockerfile` | Frontend container build |
| `frontend/package.json` | Frontend scripts and dependency metadata |

## Deployment

| Path | Responsibility |
| --- | --- |
| `Dockerfile` | Backend container build |
| `docker-compose.yml` | Canonical compose entrypoint that includes production compose wiring |
| `docker-compose.production.yml` | Production compose wiring for local validation |
| `deployment/terraform/` | AWS infrastructure modules and validation |
| `deployment/ec2/` | EC2 helper scripts and generated runtime env targets |

## Quality

| Path | Responsibility |
| --- | --- |
| `.github/workflows/ci.yml` | Backend, frontend, security, Docker, and Terraform CI checks |
| `tests/` | Backend, gateway, policy, tenant, document, and observability tests |
| `gateway-go/*_test.go` | Go gateway tests |
| `tools/verification/` | Local verification scripts and integration harnesses |
| `tools/diagnostics/` | Developer diagnostics that are not runtime code |
