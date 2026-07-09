# AuthClaw Deployment Guide

1. Configure production secrets through AWS Secrets Manager/KMS or HashiCorp Vault.
2. Set `AUTHCLAW_ENV=production`.
3. Set `AUTHCLAW_ENABLE_RBAC_ENFORCEMENT=true` unless relying on the production default.
4. Configure provider credentials per tenant or through managed provider secrets.
5. Configure OPA bundle delivery and keep `AUTHCLAW_OPA_REQUIRED=true`.
6. Provision Terraform from `deployment/terraform` or `infrastructure/terraform`.
7. Run `python scripts/terraform_config_validate.py --fail-on-missing`.
8. Run `python scripts/production_readiness_report.py --fail-on-code-gaps`.
9. Run DR validation with `python scripts/dr_readiness_validate.py --fail-on-code-gaps`.
10. Complete live AWS deployment validation, external pentest, and audit evidence outside the codebase.

Terraform now defines ECS, ALB, RDS, Redis, MSK/Kafka, CloudWatch, S3, IAM, Route53 DR controls, OPA sidecar, Secrets Manager, and customer-managed KMS.
