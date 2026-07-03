# Phase 8 Production Deployment

## Local Production-Style Testing

AuthClaw supports local production-style Docker testing without temporary PowerShell environment variables.

Create the ignored local env file once:

```powershell
Copy-Item .env.production.local.example .env.production.local
```

Then start the production compose stack:

```powershell
docker compose -f docker-compose.production.yml up -d --build
```

Local URLs:

- Frontend: `http://127.0.0.1:8080`
- Go Gateway: `http://127.0.0.1:9000`
- Python API: `http://127.0.0.1:8000`
- Readiness: `http://127.0.0.1:9000/health/ready`

The local `.env.production.local` file is intentionally gitignored. It may contain machine-specific local values and must not be committed.

## Local Configuration Model

`docker-compose.production.yml` loads `.env.production.local` with `env_file` for:

- Python governance backend
- Go Gateway
- Frontend container
- PostgreSQL

The frontend image is built with `/api` defaults so browser requests go through the production Nginx route:

```text
Browser -> frontend Nginx /api -> Go Gateway -> Python backend
```

For local testing, `.env.production.local.example` uses safe placeholder values and local-only settings:

- `AUTHCLAW_ENV=production-local`
- `AUTHCLAW_SECRET_BACKEND=local_env`
- local PostgreSQL service URL
- local document storage
- no AWS Secrets Manager
- no committed secrets

`production-local` runs the production container topology without requiring AWS-managed secrets on a developer machine.

## AWS Production Remains Unchanged

AWS production deployment still uses:

- Terraform under `deployment/terraform/`
- AWS Secrets Manager/KMS for sensitive values
- RDS PostgreSQL
- S3 document storage
- CloudWatch logging
- ECS/Fargate deployment assets

Do not use `.env.production.local` for AWS production. AWS task definitions and Terraform should continue to inject secrets from AWS Secrets Manager/KMS.

Required production secrets remain managed outside Git:

- `DATABASE_URL`
- `JWT_SECRET`
- `AUTHCLAW_ENCRYPTION_KEY`
- `AUTHCLAW_REDACTION_SALT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- provider credentials
- tenant-specific provider secrets

## Verification

After startup, verify:

```powershell
docker compose -f docker-compose.production.yml ps
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:9000/health/ready
curl http://127.0.0.1:8000/health/ready
```

Stop the local stack:

```powershell
docker compose -f docker-compose.production.yml down
```
