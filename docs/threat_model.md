# AuthClaw Threat Model

## Scope

This review covers the API backend, frontend console, Go gateway, provider credentials, approval/MFA flow, policy/redaction path, remediation workers, evidence exports, Terraform deployment, CI/CD, and operational runbooks.

## Primary Assets

- Tenant identities, sessions, and MFA factors.
- Provider credentials and tenant API keys.
- Gateway prompts, responses, redacted content, and audit events.
- Approval records, execution MFA binding records, and remediation evidence.
- Signed audit/evidence exports and Trust Center state.
- Production infrastructure state, backup recovery points, and DR routing.

## Threats And Required Controls

| Threat | Control |
| --- | --- |
| Cross-tenant data access | PostgreSQL RLS, tenant context middleware, tenant isolation tests |
| Approval or MFA bypass | Fresh action-bound MFA, replay rejection, lifecycle audit events |
| Provider credential exfiltration | Secrets Manager/KMS/Vault-backed storage, rotation audit, backend-only SDK usage |
| Prompt injection and data exfiltration | Policy blocking, OPA lifecycle, red-team harness, gateway redaction |
| PII/PHI leakage in streams | Streaming redaction fragmentation tests and performance gates |
| Audit tampering | Hash-chain verification, signed exports, tamper tests |
| Compromised dependencies or containers | Blocking Bandit, Semgrep, pip-audit, npm audit, and Trivy scans |
| Regional outage | Route53 health checks, active-active DNS, S3 replication, backup copy, DR runbook |

## Release Decision

Critical and high findings from CI scans, red-team harness, tenant isolation validation, approval bypass tests, export tamper tests, provider credential isolation tests, and DR validation must be resolved or explicitly risk-accepted before production-complete release.
