# AuthClaw AWS Production Readiness

This directory prepares AuthClaw for AWS deployment. It does not deploy anything by itself.

For a Terraform production deployment, start with [`../terraform/README.md`](../terraform/README.md). It provisions ECS Fargate, RDS PostgreSQL, Secrets Manager, S3 document storage, CloudWatch logs, an ALB, and security groups.

For a low-cost pilot deployment, start with [`100-dollar-deployment.md`](100-dollar-deployment.md). That profile uses one small ECS Fargate task, single-AZ RDS `db.t3.small`, S3/CloudFront frontend hosting, and no NAT Gateway.

For no-DNS direct EC2 testing, use [`../ec2/README.md`](../ec2/README.md) instead. That path exposes `http://<ec2-public-ip>` for the frontend and `http://<ec2-public-ip>:8000` for the backend.

## Target AWS Services

- ECS Fargate for the FastAPI gateway runtime
- RDS PostgreSQL for tenant, request, approval, and audit data
- AWS Secrets Manager for JWT, encryption, SMTP, database, and optional provider secrets
- CloudWatch Logs for API container logs
- ALB for `/health/ready` checked routing
- Route53/ACM for HTTPS DNS and certificates
- S3 for future document storage if document intelligence is retained

## Budget Guardrail

Deploy `budget-100-cloudformation.json` before the application stack to receive email alerts at 80% actual monthly spend and 100% forecasted monthly spend.

Use `rds-postgres-t3-small-cloudformation.json` to create the pilot PostgreSQL database. It provisions a private, encrypted, single-AZ RDS PostgreSQL instance using `db.t3.small` and 20 GiB gp3 storage.

## Required Production Secrets

Store these in Secrets Manager and reference them from the ECS task definition:

- `authclaw/production/database-url`
- `authclaw/production/jwt-secret`
- `authclaw/production/encryption-key`
- `authclaw/production/smtp-host`
- `authclaw/production/smtp-from`
- `authclaw/production/smtp-username`
- `authclaw/production/smtp-password`
- S3 bucket name for `AUTHCLAW_DOCUMENT_S3_BUCKET`

Optional provider secrets can be stored as JSON:

```json
{
  "api_key": "provider-key",
  "model": "provider-model",
  "api_base": "optional-provider-endpoint"
}
```

Use names such as:

- `AUTHCLAW_PROVIDER_OPENAI_SECRET_JSON`
- `AUTHCLAW_PROVIDER_ANTHROPIC_SECRET_JSON`
- `AUTHCLAW_PROVIDER_GEMINI_SECRET_JSON`
- `AUTHCLAW_TENANT_<tenant_id>_OPENAI_SECRET_JSON`

## Validation

Production startup fails unless:

- `AUTHCLAW_ENV=production`
- `JWT_SECRET` or `AUTHCLAW_JWT_SECRET` is at least 32 characters
- `AUTHCLAW_ENCRYPTION_KEY` is configured and is not the development default
- `AUTHCLAW_ALLOWED_ORIGINS` is configured and does not contain localhost, `127.0.0.1`, or `*`
- `SMTP_HOST` and `SMTP_FROM` are configured
- `AUTHCLAW_RATE_LIMIT_PER_MINUTE` is a positive integer
- `AWS_REGION` is present when `AWS_SECRETS_MANAGER_ENABLED=true`
- `AUTHCLAW_DOCUMENT_S3_BUCKET` is present when `AUTHCLAW_DOCUMENT_STORAGE_BACKEND=s3`

## Health Checks

Use:

```text
GET /health/ready
```

The endpoint checks database connectivity and production configuration state.

## Containers

- Backend image: root [`Dockerfile`](../../Dockerfile)
- Frontend image: [`../../frontend/Dockerfile`](../../frontend/Dockerfile)
- Local production smoke compose: [`../../docker-compose.production.yml`](../../docker-compose.production.yml)

## Operations

See [`backup-and-operations.md`](backup-and-operations.md) for backup, log retention, and incident checks.
