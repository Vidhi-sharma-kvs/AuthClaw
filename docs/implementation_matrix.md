# AuthClaw Implementation Matrix

| Area | Code status | Evidence | Remaining non-code dependency |
| --- | --- | --- | --- |
| RBAC | Complete for code-only scope | `services/rbac_matrix.py`, `/security/rbac/matrix`, `tests/test_production_completion_readiness.py` | Enable production enforcement and configure customer custom roles if needed |
| Trust Center | Complete for code-only scope | `services/trust_center_runtime.py`, `/trust/public`, `/trust/public/health` | Live public URL, certificate, provider credentials, customer evidence |
| Tenant isolation | Complete for logical isolation | `services/tenant_isolation_report.py`, `/security/tenant-isolation` | Physical isolation not implemented by instruction |
| KMS/Vault | Complete for code-only scope | `services/secret_manager.py`, `/security/secrets/health`, `deployment/terraform/kms.tf` | Live AWS KMS or Vault deployment and rotation drill |
| Disaster recovery | Complete for code-only scope | `scripts/dr_readiness_validate.py`, `deployment/terraform/multiregion_dr.tf` | Real two-region failover drill evidence |
| Terraform | Complete for code-only scope | `scripts/terraform_config_validate.py`, deployment/infrastructure Terraform trees | `terraform apply` against a real AWS account |
| Browser E2E | Harness added | `frontend/tests/e2e/authclaw.real-app.spec.js` | Real app credentials and Playwright runtime |

Non-code items intentionally not faked: external pentest, SOC2/HIPAA/GDPR certification, live uptime proof, real failover evidence, customer-provider production benchmark, and package-registry SDK publication.
