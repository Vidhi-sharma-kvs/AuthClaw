# API Contract Registry

This registry freezes the current AuthClaw API surface for Phase 0. It documents existing behavior and known contract mismatches without changing runtime code.

## Contract Principles

- The Go gateway remains the preferred browser/API entry point through same-origin `/api`.
- The FastAPI backend remains the canonical application API implementation.
- Frontend callers should match existing backend contracts before later feature work expands behavior.
- Any future endpoint rename, body shape change, response shape change, or route removal must update this registry.

## Runtime Entry Points

| Surface | Local URL | Notes |
| --- | --- | --- |
| Frontend | `http://127.0.0.1:5175` | Current local browser target used by the app context. |
| Go gateway | `http://127.0.0.1:9000` | Preferred API ingress for browser and client calls. |
| FastAPI backend | `http://127.0.0.1:8000` | Backend service behind gateway/reverse proxy. |
| Frontend API base | `/api` | `frontend/src/services/api.js` defaults to same-origin `/api`. |

## Gateway And Chat Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `POST` | `/gateway/chat` | Tenant-aware gateway chat through backend governance pipeline | `gatewayService.sendGatewayChatMessage` | Aligned |
| `POST` | `/chat` | Chat/session path | `chatService` fallback path | Aligned |
| `POST` | `/v1/chat/completions` | OpenAI-compatible gateway-style completion path | External clients | Existing backend contract |
| `POST` | `/gateway/documents/redact` | Gateway document redaction upload | `gatewayService.redactGatewayDocument` | Aligned |
| `GET` | `/gateway/requests` | Gateway request history | `gatewayService.getGatewayRequests` | Aligned |
| `GET` | `/gateway/requests/{request_id}` | Gateway request detail | `gatewayService.getGatewayRequestById` | Aligned |
| `GET` | `/gateway/approvals` | Gateway approval queue | `gatewayService.getGatewayApprovals` | Aligned |

## Approval Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/approvals` | List approvals | `approvalService.getApprovals` | Aligned |
| `GET` | `/approvals/{approval_id}` | Approval detail | `approvalService.getApprovalById` | Aligned |
| `GET` | `/approvals/{approval_id}/history` | Approval history | Approval/detail flows | Aligned |
| `POST` | `/approve/{approval_id}` | Approve request | `ApprovalQueue` | Aligned for current behavior |
| `POST` | `/reject/{approval_id}` | Reject request | `ApprovalQueue` | Aligned |
| `POST` | `/execute/{approval_id}` | Execute approved request | `ApprovalQueue` | Aligned for current behavior; SRS execution-MFA gap remains |

## Audit And Export Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/audit/hash-chain` | Read hash-chain audit blocks | `auditService`, dashboard, audit explorer | Aligned |
| `GET` | `/audit/verify` | Verify audit hash chain | `auditService.verifyAuditChain` | Aligned |
| `GET` | `/audit/verify/summary` | Verification summary | `auditService.getAuditSummary` | Aligned |
| `GET` | `/audit/export/csv` | Export audit CSV | Dashboard/audit explorer | Aligned |
| `GET` | `/audit/export/pdf` | Export audit PDF | Dashboard/audit explorer | Aligned |
| `GET` | `/evidence/export/csv` | Export evidence CSV | No complete frontend workspace | Backend exists; UI incomplete |
| `GET` | `/evidence/export/pdf` | Export evidence PDF | No complete frontend workspace | Backend exists; UI incomplete |
| `GET` | `/reports/{type}/{format}` | Generate report export | No complete frontend workspace | Backend exists; UI incomplete |

## Policy Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/policies` | Static/current policy view | `policyService.getPolicies` | Aligned |
| `POST` | `/policies/reload` | Reload policy config | `policyService.reloadPolicies` | Aligned |
| `GET` | `/policies/list` | List database policies | `Guardrails`, dashboard | Aligned |
| `POST` | `/policies` | Create policy | `Guardrails` | Aligned |
| `PUT` | `/policies/{policy_id}` | Update policy | `Guardrails` | Aligned |
| `DELETE` | `/policies/{policy_id}` | Delete policy | `Guardrails` | Aligned |
| `POST` | `/policies/simulate` | Simulate policy | `Guardrails` | Aligned |
| `POST` | `/policies/redact` | Redaction preview | `Guardrails` | Aligned |
| `POST` | `/policies/{policy_id}/publish` | Publish policy version | Not fully exposed | Backend exists; UI incomplete |
| `GET` | `/policies/{policy_id}/history` | Policy history | Not fully exposed | Backend exists; UI incomplete |
| `GET` | `/policies/{policy_id}/versions` | Policy versions | Not fully exposed | Backend exists; UI incomplete |
| `POST` | `/policies/{policy_id}/approve` | Approve policy change | Not fully exposed | Backend exists; UI incomplete |
| `POST` | `/policies/{policy_id}/reject` | Reject policy change | Not fully exposed | Backend exists; UI incomplete |
| `POST` | `/policies/{policy_id}/archive` | Archive policy | Not fully exposed | Backend exists; UI incomplete |
| `POST` | `/policies/{policy_id}/rollback` | Roll back policy | Not fully exposed | Backend exists; UI incomplete |
| `POST` | `/internal/policy/evaluate` | Gateway/internal policy evaluation | Go gateway | Internal contract |

## Provider Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/providers/list` | List tenant provider credentials | Dashboard, Gateway Center | Aligned |
| `POST` | `/providers/connect` | Store/connect provider credentials | Gateway Center | Mismatch: backend expects `provider` plus nested `payload`; frontend sends top-level credential fields |
| `POST` | `/providers/{provider}/rotate` | Rotate provider credential | Gateway Center intended | Mismatch: frontend uses `/providers/rotate` instead of provider path |
| `POST` | `/providers/{provider}/test` | Test provider credential | Gateway Center intended | Mismatch: frontend uses `/providers/test/{providerId}` |
| `GET` | `/providers/{provider}/health` | Provider health | Not consistently exposed | Backend exists; UI incomplete |
| `DELETE` | `/providers/{provider}` | Delete provider credential | Gateway Center | Aligned if provider identifier matches backend expectation |
| `GET` | `/providers` | Platform/provider summary | Gateway/admin routes | Existing backend contract |
| `GET` | `/providers/{provider_id}` | Provider detail | Gateway/admin routes | Existing backend contract |

Phase 0 does not correct these mismatches because the user guardrails prohibit UI behavior and provider routing changes. Phase 2 should align provider contracts.

## API Key Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `POST` | `/keys/generate` | Generate tenant API key | `APIKeys` | Aligned |
| `GET` | `/keys/list` | List tenant API keys | `APIKeys`, dashboard | Aligned |
| `DELETE` | `/keys/{key_id}` | Revoke/delete key | `APIKeys` | Aligned |
| `POST` | `/keys/{key_id}/rotate` | Rotate key | `APIKeys` | Aligned |

## Auth And Onboarding Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `POST` | `/auth/register` | Tenant registration | `Login` registration flow | Aligned |
| `POST` | `/auth/verify-email` | Email verification | `Login` onboarding flow | Aligned |
| `POST` | `/auth/verify-domain` | Domain verification | `Login` onboarding flow | Aligned |
| `POST` | `/auth/login` | Local login | `Login` | Aligned |
| `POST` | `/auth/verify-otp` | TOTP verification | `Login` MFA flow | Aligned |
| `POST` | `/auth/refresh` | Refresh token | Auth context/service path | Existing backend contract |
| `POST` | `/auth/password/reset-request` | Password reset request | `Login` | Aligned |
| `POST` | `/auth/password/reset-confirm` | Password reset confirm | `Login` | Aligned |
| `POST` | `/auth/mfa/reset-request` | MFA reset request | `Login` | Aligned |
| `POST` | `/auth/mfa/reset-confirm` | MFA reset confirm | `Login` | Aligned |

OIDC/IdP is not part of the current contract and remains a Phase 1 SRS gap.

## Document, RAG, Evidence, And Compliance Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/rag/documents` | List RAG documents | Limited/no complete admin UI | Backend exists; UI incomplete |
| `POST` | `/rag/documents` | Add RAG document | Limited/no complete admin UI | Backend exists; UI incomplete |
| `DELETE` | `/rag/documents/{doc_id}` | Delete RAG document | Limited/no complete admin UI | Backend exists; UI incomplete |
| `GET` | `/rag/chunks/{doc_id}` | Retrieve document chunks | Limited/no complete admin UI | Backend exists; UI incomplete |
| `POST` | `/rag/search` | RAG search | Limited/no complete admin UI | Backend exists; UI incomplete |
| `POST` | `/documents/upload` | Upload document | Document/chat flows | Existing backend contract |
| `POST` | `/documents/scan` | Scan document | Document/chat flows | Existing backend contract |
| `GET` | `/documents` | List documents | Limited/no complete admin UI | Backend exists; UI incomplete |
| `GET` | `/documents/{id}` | Document detail | Limited/no complete admin UI | Backend exists; UI incomplete |
| `GET` | `/documents/{id}/findings` | Document findings | Limited/no complete admin UI | Backend exists; UI incomplete |
| `GET` | `/documents/{id}/audit` | Document audit events | Limited/no complete admin UI | Backend exists; UI incomplete |
| `POST` | `/documents/chat` | Ask question over document context | Agent chat/document flows | Existing backend contract |
| `POST` | `/compliance/analyze` | Analyze compliance text/document | Limited/no complete admin UI | Backend exists; UI incomplete |
| `GET` | `/compliance/framework-scores` | Framework score summary | Dashboard/governance pages | Aligned |
| `GET` | `/evidence` | List evidence | Limited/no complete admin UI | Backend exists; UI incomplete |
| `POST` | `/evidence/collect` | Collect evidence | Limited/no complete admin UI | Backend exists; UI incomplete |
| `DELETE` | `/evidence/{id}` | Delete evidence | Limited/no complete admin UI | Backend exists; UI incomplete |

## Platform, Tenant, And Access Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/platform/summary` | Platform admin summary | Platform dashboard | Aligned |
| `GET` | `/platform/tenants` | Platform tenant list | Platform dashboard | Aligned |
| `GET` | `/tenants` | Tenant admin list | Admin routes | Existing backend contract |
| `POST` | `/tenants` | Create tenant | Admin routes | Existing backend contract |
| `PUT` | `/tenants/{tenant_id}` | Update tenant | Admin routes | Existing backend contract |
| `DELETE` | `/tenants/{tenant_id}` | Delete tenant | Admin routes | Existing backend contract |
| `GET` | `/access-control/users` | List tenant users | Settings | Aligned |
| `POST` | `/access-control/users` | Add tenant user | Settings | Aligned |

## Cloud Connector Contracts

| Method | Path | Current purpose | Frontend caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/cloud/connectors/status` | Connector status | Connectors page | Existing backend contract; real connector coverage incomplete |
| `POST` | `/cloud/connectors/sync` | Trigger connector sync | Connectors page | Existing backend contract; real connector coverage incomplete |

## Health And Metrics Contracts

| Method | Path | Current purpose | Caller | Contract status |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | Basic health | Local/runtime checks | Aligned |
| `GET` | `/health/details` | Detailed health | Diagnostics | Aligned |
| `GET` | `/health/ready` | Readiness | Gateway/ops | Aligned |
| `GET` | `/metrics` | Metrics | Dashboard/ops | Aligned |
| `GET` | `/analytics/governance` | Governance analytics | Dashboard | Aligned |

## Known Contract Gaps Deferred From Phase 0

| Gap | Current status | Reason deferred | Target phase |
| --- | --- | --- | --- |
| Provider connect body mismatch | Documented | Fixing changes frontend/API behavior | Phase 2 |
| Provider rotate URL mismatch | Documented | Fixing changes frontend/API behavior | Phase 2 |
| Provider test URL mismatch | Documented | Fixing changes frontend/API behavior | Phase 2 |
| Execution MFA missing | Documented | Fixing changes approval/security behavior | Phase 4 |
| Cohere missing | Documented | New provider behavior | Phase 2 |
| Native Azure OpenAI runtime missing | Documented | Provider routing change | Phase 2 |
| OIDC missing | Documented | Auth/session behavior change | Phase 1 |
