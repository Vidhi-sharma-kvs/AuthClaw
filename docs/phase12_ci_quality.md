# Phase 12 - CI/CD and Quality Gates

AuthClaw Phase 12 adds release safety around the gateway MVP. It does not add new product behavior; it prevents regressions in existing gateway, document redaction, tenant isolation, RBAC, MFA, provider routing, and deployment paths.

## CI Jobs

The GitHub Actions workflow at `.github/workflows/ci.yml` runs:

- Backend tests with PostgreSQL 16
- Frontend lint
- Frontend production build
- Blocking Python security scan with Bandit
- Blocking Python dependency audit with pip-audit
- Blocking Semgrep SAST scan
- Blocking frontend dependency audit
- Backend Docker build
- Blocking Trivy container scans for backend, Go gateway, and frontend images
- Frontend Docker build
- Terraform format and validation
- Deterministic red-team harness
- Release readiness report gate
- Optional live gateway benchmark through manual `workflow_dispatch`

## Test Coverage Areas

Existing suites cover the Phase 12 quality dimensions:

- Gateway: `test_gateway_chat.py`, `test_gateway_lifecycle.py`, `test_authclaw_gateway_flow.py`
- Document redaction: `test_gateway_document_redaction.py`, `test_document_intelligence.py`
- Tenant isolation: `test_tenant_isolation_hardening.py`, `test_tenant_route_isolation.py`
- RBAC: `test_auth_backend.py`, settings/API route tests in the full suite
- MFA: `test_auth_backend.py`, `test_phase8_approval_workflow.py`
- Provider router: `test_provider_router.py`, `test_phase9_secrets_management.py`
- AWS readiness: `test_phase11_aws_readiness.py`
- Latency utility: `test_gateway_benchmark.py`
- Release gates: `test_phase12_release_readiness.py`

## Blocking Security Gates

CI fails on critical/high SAST, dependency, and container findings. Critical/high
findings must be fixed or formally risk-accepted before production-complete
release.

Automated checks:

```bash
bandit -r .
pip-audit -r requirements.txt --strict
npm audit --audit-level=high
python scripts/red_team_harness.py
python scripts/release_readiness.py --strict
```

## Load and Latency

Manual live checks:

```bash
python scripts/load_test.py \
  --base-url http://13.62.54.79 \
  --api-key ac_xxx \
  --requests 25 \
  --concurrency 5 \
  --min-success-rate 0.95 \
  --max-p95-ms 5000
```

The script writes `artifacts/load-test-report.json`.

## MVP Scope Guardrail

For the first release, keep document intelligence scoped to:

1. Upload PDF/image
2. Extract text/OCR
3. Detect PII and secrets
4. Show findings
5. Generate redacted text/PDF
6. Audit the result

Document chat and RAG should remain secondary until redaction reliability is proven.
