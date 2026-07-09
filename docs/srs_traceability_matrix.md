# SRS Traceability Matrix

This matrix is the post-Phase 12 implementation status for AuthClaw. It records the current implementation state only; it does not redefine requirements or authorize runtime changes.

Status values:

- `Implemented`: Current code satisfies the requirement for the audited scope.
- `Partial`: Meaningful implementation exists but does not satisfy all SRS acceptance expectations.
- `Missing`: No complete implementation found.
- `Scaffold`: Tables, mocks, tests, or placeholders exist without production behavior.

## Functional Requirements

| SRS ref | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| FR-1.1 | Multi-model proxy for OpenAI, Anthropic, Cohere, Azure OpenAI with native payload compatibility | Implemented | Go gateway, backend provider router, provider credential APIs, provider health checks, Cohere adapter, Azure OpenAI runtime support, and contract tests exist | Live production credentials and provider-specific quota/failover drills remain operational tasks | Medium | Provider credentials, gateway runtime, observability | Phase 2 |
| FR-1.2 | Real-time PII/PHI redaction with mask, hash, and synthetic replacement | Implemented | Backend detection/redaction and Go/Python streaming fragmentation tests cover PII, PHI, secrets, and prompt-injection patterns | Encoded/compressed stream policy remains a documented constraint unless deployed at ingress | Medium | Gateway, policy engine, observability | Phase 3 |
| FR-1.3 | YAML and OPA policy enforcement with topic and regex blocking | Implemented | YAML validation, policy lifecycle, OPA/Rego assets, production OPA requirement flags, promotion/rollback tests, and gateway enforcement paths exist | OPA operational bundle hosting must be configured in production deployment | Medium | OPA deployment, CI policy tests | Phase 3 |
| FR-2.1 | Orchestrator-worker isolation with scoped temporary tokens | Implemented | Remediation runtime APIs, tenant-scoped connectors, worker runs, temporary credential leases, plans, evidence, audit events, AWS/GCP/GitHub adapter paths, and isolation tests exist | Real cloud accounts must be onboarded and validated per customer tenant | Medium | Secrets, HITL approvals, worker runtime | Phase 5 |
| FR-2.2 | Context-aware framework querying via RAG over regulatory docs | Implemented | Control catalog, corpus versioning, evidence mapping, control-level scoring, score-change reasons, exportable evidence, and drift tests exist | Production vector backend sizing remains deployment-specific | Medium | Evidence engine, vector backend, audit pipeline | Phase 6 |
| FR-2.3 | HITL workflow with pending approval, 0.5 hour expiry, and MFA on execution | Implemented | Approval MFA and fresh execution MFA are action-bound to tenant, approver, approval ID, payload hash, expiry, stage, and TOTP counter; execution is single-use and audited | Customer MFA enrollment coverage is an operational prerequisite | Medium | MFA, approval API, frontend approvals, audit | Phase 4 |
| FR-3.1 | Automated framework scoring for SOC2, GDPR, HIPAA | Implemented | Framework scores are traceable to control evidence, source events, timestamps, and score-change reasons | External auditor interpretation may require customer-specific control mappings | Medium | Evidence model, audit, documents, remediation | Phase 6 |
| FR-3.2 | Cryptographically verified audit export | Implemented | Signed export manifest, independent verifier endpoint, Trust Center live state, tamper tests, and auditor package export exist | External key custody policy must be selected per enterprise deployment | Medium | Audit ledger, key management, export service, Trust Center | Phase 7 |

## Platform And Product Scope

| SRS area | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Authentication | Registration, login, email verification, domain verification, MFA | Implemented for local auth | Tenant registration, email/domain verification, local login, TOTP, refresh tokens, password/MFA reset exist | Enterprise IdP is separate and missing | Large | OIDC config, tenant mapping, frontend login | Phase 1 |
| Authentication | OIDC/IdP auth | Implemented | Tenant IdP configuration, OIDC/JWKS assets, IdP docs, and identity provider APIs exist | Enterprise group-claim mapping must be validated for each IdP | Medium | Auth service, RBAC, tenant config | Phase 1 |
| RBAC | Multi-tenant role-based access control | Partial | Roles, protected frontend routes, tenant-scoped APIs, and selected backend admin checks exist | Complete permission matrix for every admin API is still not fully proven | Medium | Auth service, permission model, tests | Phase 12 residual |
| API keys | Tenant API key admin | Implemented | Generate, list, delete, rotate APIs and UI exist | No Phase 0 change required | Small | Existing auth/tenant context | Complete |
| Provider credentials | Store, test, rotate provider credentials | Implemented | Backend credentials APIs, frontend provider UI, provider health, contract tests, Cohere, and native Azure support exist | Production credential rotation drills remain operational | Small | API contract, provider adapters, frontend service | Phase 2 |
| Gateway | Go reverse proxy and policy preflight | Implemented | Go gateway provides health endpoints, proxying, policy evaluation, stream redaction, audit event emission, provider contracts, and benchmark harnesses | Live provider latency must be measured per environment | Medium | Provider adapters, OPA, benchmark harness | Phases 2, 3, 9 |
| Public Trust Center | Public compliance/trust page | Implemented | Public frontend Trust Center consumes live signed state and exposes verification metadata | Customer-selected public evidence scope must be configured | Small | Evidence engine, signed exports, public verifier | Phase 7 |
| SDK | Customer SDK | Implemented | Production Python SDK includes typed wrappers, retries, timeouts, streaming, errors, provider/API key/approval/remediation/audit helpers, and docs | Publishing to a package registry is an operational release task | Small | OpenAPI, stable contracts, docs | Phase 11 |

## Non-Functional Requirements

| SRS ref | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NFR-1.1 | <=50 ms gateway overhead | Implemented | Gateway benchmark harness compares baseline/provider latency and CI enforces `--max-overhead-ms 50` when live benchmark credentials are configured | Live benchmark environment must be supplied for production proof | Medium | Benchmark harness, telemetry, provider mocks | Phase 9 |
| NFR-1.2 | Token-by-token streaming filtering with no fragmentation | Implemented | Go and Python streaming tests cover adversarial fragmentation and load budgets | Compressed/encoded streams require ingress decoding policy | Medium | Gateway streaming, redaction engine, performance tests | Phase 3 |
| NFR-2.1 | Tenant isolation through RLS or physical isolation | Partial | Many tenant tables use Postgres RLS and tenant context helpers | Some tenant-relevant tables are not fully covered; no physical isolation option exists | Medium | Schema review, migrations, tests | Phase 1 |
| NFR-2.2 | Envelope encryption AES-256-GCM via KMS or Vault for client credentials | Partial | Secret manager abstractions and local encryption exist; AWS Secrets Manager paths exist | Production KMS/Vault enforcement and rotation model are incomplete | Medium | KMS/Vault, Terraform, credential APIs | Phase 1 |
| NFR-3.1 | 99.99% uptime, multi-region active-active | Partial | Optional Route53 active-active DNS, regional deployment model, S3 replication, AWS Backup cross-region copy, DR validation script, chaos scenarios, and runbook exist | Actual 99.99% uptime requires deployed two-region environment and completed failover drill evidence | Large | Terraform, DNS, data stores, CI/CD, monitoring | Phase 10 residual |
| NFR-3.2 | Tiered rate limiting and background scan throttling | Implemented | Redis-backed distributed limiter, DB fallback telemetry, worker throttling, Terraform Redis provisioning, metrics, and tests exist | Commercial tenant plan packaging remains business configuration | Small | Redis, tenant plans, worker queues | Phase 8 |

## Infrastructure, CI/CD, And Operations

| Area | Requirement | Current status | Current implementation | Gap | Complexity | Dependencies | Target phase |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Docker | Local production-like stack | Implemented | Compose includes API, gateway, frontend, Postgres, Kafka, ClickHouse, and OPA | Not a substitute for production HA | Small | Existing compose | Complete |
| Terraform | ECS, ALB, CloudWatch, RDS, S3, secrets | Partial | Terraform baseline now includes ECS, ALB, CloudWatch, RDS, S3, secrets, Redis, MSK/analytics controls, Route53 DR, backup copy, and S3 replication | OPA service and full customer-managed KMS key topology remain deployment-specific | Medium | Terraform modules, AWS services | Phase 10 residual |
| CI/CD | Build, test, security scan, container build, promotion gates | Implemented | Backend, frontend, Go, Docker, Terraform, performance, blocking SAST/dependency/container scans, promotion workflow, red-team harness, and readiness gate exist | External pentest report/risk acceptance is still an operational release artifact | Medium | GitHub Actions, environments, release policy | Phase 12 |
| Observability | Metrics, analytics, audit health | Implemented | Durable event pipeline, Kafka/MSK controls, analytics sink, DLQ/retry, Redis limiter metrics, worker throttling, and dashboard cards exist | Alert routing configuration is environment-specific | Small | Kafka, ClickHouse/equivalent, alerting, dashboard | Phase 8 |
| Disaster recovery | Backup, restore, failover, runbooks | Partial | DR Terraform controls, validation harness, runbook, chaos scenarios, promotion workflow, and RTO/RPO documentation exist | Regional failover evidence must be produced from a deployed two-region environment | Large | Terraform, data stores, ops runbooks | Phase 10 residual |
| Testing coverage | Unit, integration, gateway, policy, auth, document tests | Partial | Broad backend, Go, provider, policy, approval, remediation, evidence, signed export, observability, performance, DR, SDK, and release-readiness tests exist | Browser E2E coverage across every console workflow remains incomplete | Large | Test harnesses, implemented features | Phase 12 residual |

## Scaffold And Placeholder Inventory

| Area | Status | Current artifact | Required resolution phase |
| --- | --- | --- | --- |
| Python SDK | Implemented | `sdk/python/` | Production package publishing remains operational |
| Ephemeral workers | Implemented | Worker runtime, leases, findings, plans, evidence | Cloud credentials must be configured per tenant |
| Cloud connectors | Implemented | AWS/GCP/GitHub runtime paths with mocks in tests | Customer cloud onboarding remains operational |
| Kafka audit emission | Implemented | Durable delivery records, Kafka REST/MSK controls, DLQ/retry | Kafka REST proxy endpoint must be configured |
| Red-team/pentest | Partial | Deterministic red-team harness, CI gate, threat model, release report | External pentest execution remains outside repository automation |
| HA status | Partial | DR topology, validation harness, runbook, RTO/RPO outputs | Live regional failover evidence required |
| Placeholder tests | Partial | Focused coverage added through phases 1-12 | Full frontend browser E2E remains residual |

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
