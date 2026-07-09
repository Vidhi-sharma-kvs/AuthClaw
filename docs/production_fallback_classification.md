# Production Fallback Classification

This document classifies known AuthClaw fallback, mock, scaffold, and bypass behavior for Phase 0. It does not change runtime behavior.

Classification values:

- `Local-dev allowed`: Acceptable for local development and tests only.
- `Production degraded-mode allowed`: Acceptable in production only if observable, controlled, and documented.
- `Production forbidden`: Must not be enabled or relied on in production.
- `Scaffold`: Exists to reserve structure or support tests, but is not production-complete.

## Authentication And Approval

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| `DISABLE_MFA_FOR_TESTING` and `AUTHCLAW_ALLOW_TEST_MFA_BYPASS` | Auth/MFA helpers and local scripts | Production forbidden | Must remain disabled in production | Phase 1 |
| Legacy empty-body approval bypass | Approval endpoint and HITL tests | Production forbidden | Must be removed or blocked before production-complete release | Phase 4 |
| Email delivery soft bypass for reset/onboarding when SMTP fails | Auth reset/onboarding flows | Local-dev allowed | Production must use configured email delivery and alert on failures | Phase 1 |
| Default MFA code in policy config validation | `policies.yaml`, startup validation | Production forbidden unless strictly test-scoped | Must not be accepted as a production approval factor | Phase 4 |

## Provider And LLM Runtime

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| Offline LLM fallback response | `nodes/llm_node.py` | Local-dev allowed | Production should fail closed or surface provider outage explicitly without synthetic success | Phase 2 |
| Legacy provider fallback source | Provider router and LLM node | Local-dev allowed | Production provider route must be tenant/provider explicit | Phase 2 |
| Missing external provider keys allowing degraded local behavior | Startup validation | Local-dev allowed | Production must require configured provider credentials or tenant-provided credentials | Phase 2 |
| Gemini/deterministic provider behavior used for tests | Tests and local paths | Local-dev allowed | Must remain test-only | Phase 2 |

## Redaction, Policy, And Gateway

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| Python/YAML policy fallback when OPA is unavailable | Policy engine and Go gateway fallback path | Production degraded-mode allowed only with alerting | Production should make OPA availability explicit and auditable | Phase 3 |
| OPA default allow policy asset | Rego assets | Production degraded-mode allowed only with complete policy bundles | Production policy bundles must be reviewed and tested | Phase 3 |
| Safe placeholder on stream redaction failure | Go gateway redacting body | Production degraded-mode allowed | Acceptable if audited and alerting is configured | Phase 3 |
| Encoded stream rejection when stream cannot be inspected | Go gateway | Production degraded-mode allowed | Acceptable fail-closed behavior if documented to clients | Phase 3 |

## Document Intelligence And RAG

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| `AUTHCLAW_DISABLE_BACKGROUND_MONITOR` | Local scripts and backend startup | Local-dev allowed | Must remain disabled only for local/manual test runs | Phase 8 |
| `AUTHCLAW_DISABLE_REMOTE_EMBEDDINGS` | RAG embeddings | Local-dev allowed | Production should use approved embedding provider or production vector strategy | Phase 6 |
| Deterministic fallback embeddings | RAG embeddings | Local-dev allowed | Not sufficient for production search quality claims | Phase 6 |
| Local document-answer fallback when Gemini is offline | Document chat/compliance paths | Local-dev allowed | Production should expose degraded provider status clearly | Phase 6 |
| Parser dependency fallbacks | Document parsers | Production degraded-mode allowed | Acceptable if format support matrix is documented and failures are audited | Phase 6 |

## Cloud Connectors And Remediation

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| `ENABLE_REAL_CONNECTORS=false` mock connector mode | Document/cloud connectors | Scaffold/local-dev allowed | Production cloud connector claims require real connector mode and credential validation | Phase 5 |
| Mock S3/GDrive/OneDrive/SharePoint/Dropbox payloads | Connector fetch/list paths | Scaffold | Must not be presented as real customer evidence in production | Phase 5 |
| Mock compliance findings for cloud checks | Connector/compliance paths | Scaffold | Must not feed production framework scoring as real evidence | Phase 6 |
| Missing GitHub remediation connector | Connector/remediation scope | Missing | Required for SRS agentic remediation scope | Phase 5 |

## Audit, Analytics, And Observability

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| Kafka audit scaffold logging when no Kafka REST URL exists | Go audit producer | Scaffold/local-dev allowed | Production must use durable event delivery or explicit fail/alert behavior | Phase 8 |
| PostgreSQL analytics fallback when ClickHouse is unavailable | Observability service | Production degraded-mode allowed | Acceptable temporarily if visible and alerted | Phase 8 |
| Best-effort ClickHouse mirror | Audit verification/mirroring | Production degraded-mode allowed only with retry/loss accounting | Production audit pipeline needs delivery guarantees | Phase 8 |
| Static Trust Center content | Frontend public page | Scaffold/partial | Production Trust Center must be backed by live signed evidence | Phase 7 |

## Infrastructure And CI/CD

| Behavior | Current location | Classification | Production rule | Target phase |
| --- | --- | --- | --- | --- |
| Non-blocking Bandit/npm audit behavior | CI workflow | Production forbidden for release gates | Security scans should block production promotion except approved exceptions | Phase 12 |
| Single-region Terraform baseline | Terraform | Scaffold/partial | Does not satisfy active-active or 99.99% SRS target | Phase 10 |
| Docker Compose Kafka/ClickHouse/OPA | Compose | Local-dev allowed | Not a production HA substitute | Phase 8 |
| Placeholder SDK | `sdk/python/` | Scaffold | Must not be marketed as complete production SDK | Phase 11 |

## Phase 0 Production Configuration Policy

Until later phases close these gaps, production deployments should:

- Disable all test MFA and onboarding bypass flags.
- Require explicit SMTP configuration for user-facing auth flows.
- Require tenant/provider credentials instead of offline LLM fallbacks.
- Treat mock connector output as non-evidence.
- Alert on OPA, Kafka, ClickHouse, and provider degraded modes.
- Keep signed export and Trust Center claims scoped to currently implemented hash-chain/HMAC behavior.
- Avoid claiming active-active, 99.99% uptime, Cohere support, native Azure OpenAI routing, or scoped remediation workers until the corresponding target phases are complete.
