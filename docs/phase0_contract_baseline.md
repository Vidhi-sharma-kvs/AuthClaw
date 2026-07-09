# Phase 0 Contract Baseline

Phase 0 establishes the implementation baseline for AuthClaw without changing runtime behavior. It records what the current production code does, where it diverges from the SRS, and which contracts later phases must preserve or intentionally change through a controlled plan.

## Non-Negotiable Guardrails

This phase does not modify:

- Business logic
- Authentication, JWT, session, MFA, or TOTP flows
- PostgreSQL RLS or tenant isolation behavior
- Provider routing logic
- Go gateway behavior
- Existing API implementations
- Frontend behavior or routing
- Existing features

The current codebase is treated as production. Any behavior gap is documented as a contract or SRS gap rather than changed in this phase.

## Phase 0 Artifacts

| Artifact | Purpose |
| --- | --- |
| `docs/srs_traceability_matrix.md` | Maps SRS requirements to current implementation status, owning modules, gaps, dependencies, and recommended delivery phase. |
| `docs/api_contract_registry.md` | Freezes the current backend, gateway, and frontend API contract surface, including documented mismatches. |
| `docs/production_fallback_classification.md` | Classifies local-dev fallbacks, production-allowed degraded modes, and production-forbidden bypass/scaffold behavior. |
| `docs/phase0_contract_baseline.md` | Records the Phase 0 scope, constraints, acceptance criteria, and outcome. |

## Contract Freeze Rules

- Existing endpoints remain the canonical current contract until a later phase explicitly changes them.
- Frontend/backend mismatches are documented, not corrected, in Phase 0.
- Mock, fallback, and scaffold paths are classified by production acceptability.
- Missing SRS requirements are assigned to later delivery phases.
- Any later breaking change must update the contract registry and traceability matrix in the same change set.

## Phase 0 Acceptance Criteria

| Criterion | Status |
| --- | --- |
| Every SRS functional requirement has an implementation status. | Complete |
| Every SRS non-functional requirement has an implementation status. | Complete |
| Partially implemented and missing features are assigned dependencies and future phases. | Complete |
| API route groups are documented from the current codebase. | Complete |
| Known frontend/backend contract mismatches are documented. | Complete |
| Production-forbidden fallbacks and bypasses are identified. | Complete |
| No runtime code, auth, gateway, RLS, provider routing, or UI behavior is changed. | Complete |

## Current Baseline Summary

AuthClaw currently has a strong local/product MVP baseline:

- FastAPI backend with tenant onboarding, local auth, MFA, API keys, approvals, policies, audit, documents, providers, analytics, and admin APIs.
- Go gateway with reverse proxy behavior, policy preflight, streaming response redaction, health checks, and audit event emission.
- React/Vite console with dashboard, gateway, provider, policy, approval, audit, connector, API key, chat, and public trust pages.
- Docker Compose stack for local API, gateway, frontend, Postgres, Kafka, ClickHouse, and OPA.
- Terraform baseline for ECS, ALB, RDS, S3, Secrets Manager, CloudWatch, and related AWS resources.

The main remaining SRS gaps are enterprise IdP/OIDC, complete four-provider gateway support, production OPA lifecycle, SRS-grade streaming redaction guarantees, action-bound execution MFA, ephemeral scoped remediation workers, evidence-backed framework scoring, auditor-grade signed exports, production Kafka/ClickHouse/Redis infrastructure, active-active multi-region deployment, DR validation, and performance proof for the <=50 ms gateway overhead target.

## Next Required Phase

Phase 1 should begin with security and tenant foundation work:

- Enterprise OIDC/IdP
- Route-level RBAC hardening
- Full tenant-scope table review
- Production bypass controls
- Production KMS/Vault enforcement model

Those changes are intentionally outside Phase 0.
