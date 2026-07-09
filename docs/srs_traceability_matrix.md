# SRS Traceability Matrix

This matrix is the Phase 0 baseline for AuthClaw. It records the current implementation state only; it does not redefine requirements or authorize runtime changes.

Status values:

- `Implemented`: Current code satisfies the requirement for the audited scope.
- `Partial`: Meaningful implementation exists but does not satisfy all SRS acceptance expectations.
- `Missing`: No complete implementation found.
- `Scaffold`: Tables, mocks, tests, or placeholders exist without production behavior.

## Functional Requirements

| SRS ref | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-1.1 | Multi-model proxy for OpenAI, Anthropic, Cohere, Azure OpenAI with native payload compatibility | Partial | Go gateway plus Python provider router support OpenAI, Anthropic, and Gemini paths; Azure credential validation exists | Cohere missing; Azure OpenAI runtime path is not native; native provider payload compatibility is not fully proven | Large | Provider adapters, credentials, gateway contracts, frontend provider UI, tests | Phase 2 |
| FR-1.2 | Real-time PII/PHI redaction with mask, hash, and synthetic replacement | Partial | Backend sensitive data detection supports masking, hashing/fingerprints, synthetic replacement, blocking, and approval actions | Sync path is stronger than streaming path; production guarantees are not proven across all gateway/provider paths | Large | Redaction engine, gateway stream redactor, policy engine, test harness | Phase 3 |
| FR-1.3 | YAML and OPA policy enforcement with topic and regex blocking | Partial | YAML policies, Python policy engine, OPA/Rego assets, gateway OPA preflight, policy CRUD/versioning/simulation exist | OPA is not the sole production enforcement lifecycle; policy bundle management and coverage are incomplete | Medium | Policy schema, OPA deployment, validation, CI policy tests | Phase 3 |
| FR-2.1 | Orchestrator-worker isolation with scoped temporary tokens | Scaffold | LangGraph-style orchestration and database tables for workers/findings exist | No complete isolated worker runtime, temporary scoped cloud tokens, or bounded execution lifecycle | Large | Secrets, worker runtime, cloud connectors, HITL, audit | Phase 5 |
| FR-2.2 | Context-aware framework querying via RAG over regulatory docs | Partial | RAG ingestion, regulatory text files, document chunks, embeddings, search, and compliance analyzer exist | Retrieval uses local/Postgres-style vector handling and fallback embeddings; corpus lifecycle and production-scale vector search are incomplete | Medium | Vector backend, corpus versioning, evidence model | Phase 6 |
| FR-2.3 | HITL workflow with pending approval, 0.5 hour expiry, and MFA on execution | Partial | Approval records, 30-minute expiry, comments, audit, approve/reject/execute endpoints, and MFA during approval exist | Fresh action-bound MFA at execution is missing; legacy empty-body approval bypass exists | Large | MFA service, approval API, frontend approvals, audit | Phase 4 |
| FR-3.1 | Automated framework scoring for SOC2, GDPR, HIPAA | Partial | Framework scores, governance analytics, document scan findings, and compliance analysis exist | Scoring is heuristic/aggregate-based rather than fully evidence-backed per control | Large | Evidence model, control catalog, audit, documents, remediation | Phase 6 |
| FR-3.2 | Cryptographically verified audit export | Partial | Hash-chain audit verification, CSV/PDF exports, and HMAC-style signing helpers exist | Auditor-grade independent verification, signed manifests, public verification, and asymmetric trust model are incomplete | Medium | Audit ledger, key management, export service, Trust Center | Phase 7 |

## Platform And Product Scope

| SRS area | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication | Registration, login, email verification, domain verification, MFA | Implemented for local auth | Tenant registration, email/domain verification, local login, TOTP, refresh tokens, password/MFA reset exist | Enterprise IdP is separate and missing | Large | OIDC config, tenant mapping, frontend login | Phase 1 |
| Authentication | OIDC/IdP auth | Missing | Local JWT/password/TOTP model exists | No tenant IdP configuration, OIDC callback, JWKS validation, SSO, or IdP group sync | Large | Auth service, RBAC, tenant config | Phase 1 |
| RBAC | Multi-tenant role-based access control | Partial | Roles and protected frontend routes exist; backend has selected admin checks | Route-level backend RBAC is not complete across all sensitive APIs | Medium | Auth service, permission model, tests | Phase 1 |
| API keys | Tenant API key admin | Implemented | Generate, list, delete, rotate APIs and UI exist | No Phase 0 change required | Small | Existing auth/tenant context | Complete |
| Provider credentials | Store, test, rotate provider credentials | Partial | Backend credentials APIs and frontend provider UI exist | Frontend/backend contract mismatches exist for connect/test/rotate; Cohere and native Azure incomplete | Medium | API contract, provider adapters, frontend service | Phase 2 |
| Gateway | Go reverse proxy and policy preflight | Partial | Go gateway provides health endpoints, proxying, policy evaluation, stream redaction, and audit event emission | SRS provider completeness, streaming guarantees, and performance proof remain incomplete | Large | Provider adapters, OPA, benchmark harness | Phases 2, 3, 9 |
| Public Trust Center | Public compliance/trust page | Partial | Public frontend Trust Center page exists | Not backed by complete live evidence, signed export verification, or public verifier | Medium | Evidence engine, signed exports, public verifier | Phase 7 |
| SDK | Customer SDK | Scaffold | Python SDK placeholder/lightweight client exists | Not a production SDK with typed models, retries, package maturity, and full API coverage | Medium | OpenAPI, stable contracts, docs | Phase 11 |

## Non-Functional Requirements

| SRS ref | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NFR-1.1 | <=50 ms gateway overhead | Missing proof | Benchmark scripts and CI hooks exist | No accepted benchmark proves overhead target; CI threshold does not enforce this requirement | Medium | Benchmark harness, telemetry, provider mocks | Phase 9 |
| NFR-1.2 | Token-by-token streaming filtering with no fragmentation | Partial | Go streaming redactor exists with split-pattern tests | Not proven for token-by-token provider streams, all detector classes, backpressure, and no-fragmentation semantics | Large | Gateway streaming, redaction engine, performance tests | Phase 3 |
| NFR-2.1 | Tenant isolation through RLS or physical isolation | Partial | Many tenant tables use Postgres RLS and tenant context helpers | Some tenant-relevant tables are not fully covered; no physical isolation option exists | Medium | Schema review, migrations, tests | Phase 1 |
| NFR-2.2 | Envelope encryption AES-256-GCM via KMS or Vault for client credentials | Partial | Secret manager abstractions and local encryption exist; AWS Secrets Manager paths exist | Production KMS/Vault enforcement and rotation model are incomplete | Medium | KMS/Vault, Terraform, credential APIs | Phase 1 |
| NFR-3.1 | 99.99% uptime, multi-region active-active | Missing | Single-region-style Terraform baseline exists | No active-active topology, global routing, replication, failover, or chaos validation | Large | Terraform, DNS, data stores, CI/CD, monitoring | Phase 10 |
| NFR-3.2 | Tiered rate limiting and background scan throttling | Partial | Optional Redis/in-memory rate limiter exists | Redis is not provisioned; tier model and worker throttling are incomplete | Medium | Redis, tenant plans, worker queues | Phase 8 |

## Infrastructure, CI/CD, And Operations

| Area | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Docker | Local production-like stack | Implemented | Compose includes API, gateway, frontend, Postgres, Kafka, ClickHouse, and OPA | Not a substitute for production HA | Small | Existing compose | Complete |
| Terraform | ECS, ALB, CloudWatch, RDS, S3, secrets | Partial | Terraform baseline exists for major AWS resources | Missing active-active, managed Kafka, ClickHouse, Redis, OPA service, and full KMS model | Large | Terraform modules, AWS services | Phase 10 |
| CI/CD | Build, test, security scan, container build, promotion gates | Partial | Backend, frontend, Go, Docker, and Terraform checks exist | Security scans are not fully blocking; deployment promotion gates are incomplete | Medium | GitHub Actions, environments, release policy | Phase 12 |
| Observability | Metrics, analytics, audit health | Partial | Metrics, governance analytics, audit verification, ClickHouse schema, and dashboard exist | Production ingestion pipeline and delivery guarantees are incomplete | Large | Kafka, ClickHouse, alerting, dashboard | Phase 8 |
| Disaster recovery | Backup, restore, failover, runbooks | Missing | Some deployment/backup documentation exists | No validated RTO/RPO, restore drill, active failover, or chaos evidence | Large | Terraform, data stores, ops runbooks | Phase 10 |
| Testing coverage | Unit, integration, gateway, policy, auth, document tests | Partial | Broad backend and Go tests exist | Frontend E2E, provider contract, DR, streaming, performance, OIDC, and worker tests are missing | Large | Test harnesses, implemented features | Phases 2-12 |

## Scaffold And Placeholder Inventory

| Area | Status | Current artifact | Required resolution phase |
| --- | --- | --- | --- |
| Python SDK | Scaffold | `sdk/python/` | Phase 11 |
| Ephemeral workers | Scaffold | Worker/finding tables and orchestration concepts | Phase 5 |
| Cloud connectors | Partial/scaffold | Connector module with mock-mode fallbacks | Phase 5 |
| Kafka audit emission | Scaffold/partial | Local Kafka REST path plus scaffold logging fallback | Phase 8 |
| Red-team/pentest | Scaffold | Tables/tests/docs without complete harness | Phase 12 |
| HA status | Scaffold | HA status persistence concepts | Phase 10 |
| Placeholder tests | Scaffold | Approval, graph, chunker, retriever placeholder tests | Phase 12 |

## Phase Assignment Summary

| Phase | Primary SRS gap group |
| --- | --- |
| Phase 1 | Security foundation, OIDC, RBAC, tenant isolation, KMS/Vault |
| Phase 2 | Provider gateway completion and provider API contract alignment |
| Phase 3 | OPA lifecycle, policy hardening, streaming redaction guarantees |
| Phase 4 | HITL execution MFA and approval security |
| Phase 5 | Ephemeral scoped remediation workers and cloud connectors |
| Phase 6 | Evidence-backed framework scoring and production RAG |
| Phase 7 | Signed exports and live Trust Center verification |
| Phase 8 | Kafka, ClickHouse, Redis, observability, and throttling |
| Phase 9 | Performance/load validation and <=50 ms gateway overhead proof |
| Phase 10 | Multi-region active-active deployment and DR |
| Phase 11 | SDK and developer/operations documentation |
| Phase 12 | Security validation, pentest, red-team, and release readiness |
