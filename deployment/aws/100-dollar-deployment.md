# AuthClaw $100/month AWS Deployment Plan

This profile is for a small production pilot, not high availability. It keeps AuthClaw usable as an AI Governance Gateway while avoiding expensive AWS defaults such as NAT Gateways and oversized compute.

## Target URLs

- Dashboard: `https://app.authclaw.example.com`
- Gateway API: `https://api.authclaw.example.com`
- Gateway endpoint used by customer apps: `POST https://api.authclaw.example.com/gateway/chat`

## Monthly Budget Shape

Approximate low-traffic target:

| Service | Budget profile |
| --- | --- |
| ECS Fargate | 1 task, 0.5 vCPU, 1 GB RAM |
| Application Load Balancer | 1 public ALB |
| RDS PostgreSQL | single-AZ `db.t3.small`, 20 GB gp3 storage |
| Frontend | S3 static hosting plus CloudFront |
| Secrets Manager | JWT, encryption key, SMTP, database URL, provider bootstrap secrets |
| CloudWatch | short retention, low-volume logs |
| Route53 + ACM | hosted zone, DNS records, free ACM certificate |

Keep provider LLM spend outside this estimate; OpenAI/Gemini/Anthropic/Azure usage is billed by the provider account configured by each tenant.

## Cost Controls

1. Use `desiredCount: 1` in `ecs-service.json`.
2. Use `cpu: 512` and `memory: 1024` in `ecs-task-definition.json`.
3. Do not create a NAT Gateway for this pilot. Put the API task in public subnets with `assignPublicIp: ENABLED`, and restrict inbound traffic to the ALB security group.
4. Use a single-AZ RDS `db.t3.small` instance for the pilot.
5. Set CloudWatch retention to 7 or 14 days.
6. Deploy `budget-100-cloudformation.json` before the application stack.
7. Keep document scanning/background workers disabled or low-frequency until the pilot budget is increased.

## Required AWS Resources

Create these once:

1. VPC with two public subnets.
2. Public ALB with HTTPS listener.
3. ECS cluster for the API container.
4. RDS PostgreSQL `db.t3.small` instance from `rds-postgres-t3-small-cloudformation.json`.
5. S3 bucket for frontend static files.
6. CloudFront distribution for the dashboard.
7. Route53 records:
   - `app.authclaw.example.com` -> CloudFront
   - `api.authclaw.example.com` -> ALB
8. ACM certificates for both hostnames.
9. AWS Secrets Manager entries listed in `README.md`.
10. AWS Budget stack from `budget-100-cloudformation.json`.

## Production Environment

Backend environment must be based on `env.production.template`.

Required production values:

```env
AUTHCLAW_ENV=production
AUTHCLAW_ALLOWED_ORIGINS=https://app.authclaw.example.com
ENABLE_DEV_MODE=false
SKIP_EMAIL_DELIVERY_FOR_TESTING=false
SKIP_DOMAIN_VERIFICATION=false
DISABLE_MFA_FOR_TESTING=false
JWT_SECRET=<32+ character secret from Secrets Manager>
AUTHCLAW_ENCRYPTION_KEY=<Fernet key from Secrets Manager>
DATABASE_URL=<RDS PostgreSQL URL from Secrets Manager>
SMTP_HOST=<SES or SendGrid SMTP host>
SMTP_FROM=no-reply@authclaw.example.com
AUTHCLAW_RATE_LIMIT_PER_MINUTE=120
```

Frontend build must use `frontend.env.production.template`:

```env
VITE_API_BASE_URL=https://api.authclaw.example.com
```

## Security Group Rules

ALB security group:

- Inbound: `443` from internet
- Outbound: API task security group on `8000`

API task security group:

- Inbound: `8000` from ALB security group only
- Outbound: `443` to internet for LLM providers and SMTP/Secrets Manager where needed
- Outbound: `5432` to RDS security group

RDS security group:

- Inbound: `5432` from API task security group only

## Deployment Steps

1. Create the monthly budget alert:

```bash
aws cloudformation deploy \
  --stack-name authclaw-budget \
  --template-file deployment/aws/budget-100-cloudformation.json \
  --parameter-overrides BudgetEmail=<alerts@example.com> BudgetLimitUsd=100
```

2. Create the RDS PostgreSQL database with `db.t3.small`:

```bash
aws cloudformation deploy \
  --stack-name authclaw-rds \
  --template-file deployment/aws/rds-postgres-t3-small-cloudformation.json \
  --parameter-overrides \
    VpcId=<vpc-id> \
    PrivateSubnetIds=<private-subnet-a>,<private-subnet-b> \
    ApiTaskSecurityGroupId=<sg-authclaw-api> \
    DatabaseUsername=authclaw \
    DatabasePassword=<generated-strong-password>
```

Store the resulting PostgreSQL connection string in Secrets Manager as `authclaw/production/database-url`.

3. Build and push backend image:

```bash
docker build -t authclaw-api:production .
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag authclaw-api:production <account-id>.dkr.ecr.us-east-1.amazonaws.com/authclaw-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/authclaw-api:latest
```

4. Build frontend:

```bash
cd frontend
VITE_API_BASE_URL=https://api.authclaw.example.com npm run build
aws s3 sync dist/ s3://<frontend-bucket> --delete
aws cloudfront create-invalidation --distribution-id <distribution-id> --paths "/*"
```

5. Register task definition:

```bash
aws ecs register-task-definition --cli-input-json file://deployment/aws/ecs-task-definition.json
```

6. Create or update service:

```bash
aws ecs create-service --cli-input-json file://deployment/aws/ecs-service.json
```

For existing service:

```bash
aws ecs update-service --cluster authclaw-production --service authclaw-gateway --force-new-deployment
```

7. Verify:

```bash
curl https://api.authclaw.example.com/health/ready
curl https://api.authclaw.example.com/openapi.json
```

## Product Verification

After deployment:

1. Register a tenant from the dashboard.
2. Verify email through production SMTP.
3. Verify domain with DNS TXT.
4. Generate an AuthClaw API key.
5. Connect at least one provider credential.
6. Send a request to `/gateway/chat` with the AuthClaw API key.
7. Confirm Requests, Request Detail, and Audit Logs show the request and agent trace.

## Known Pilot Tradeoffs

- This profile is not multi-AZ highly available.
- No NAT Gateway is used to keep cost down.
- One API task means deployments may briefly reduce capacity.
- Increase to two ECS tasks and multi-AZ RDS when budget allows.
