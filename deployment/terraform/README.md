# AuthClaw Terraform Production Stack

This stack prepares a production-shaped AuthClaw deployment on AWS without embedding secrets in the repository.

## Resources

- VPC with public and private subnets
- ALB with health checks for frontend and API
- ECS Fargate service running:
  - `authclaw-api`
  - `authclaw-frontend`
- RDS PostgreSQL `db.t3.small` by default
- AWS Secrets Manager for database URL, JWT, encryption key, and SMTP credentials
- S3 private encrypted document bucket
- CloudWatch log groups, retention, and an unhealthy-target alarm
- Security groups scoped to ALB -> ECS -> RDS
- VPC endpoints for Secrets Manager, CloudWatch Logs, ECR, and S3

## Build Images

```bash
docker build -t authclaw-api:latest -f Dockerfile .
docker build -t authclaw-frontend:latest -f frontend/Dockerfile frontend
```

Push both images to ECR and set `api_image` and `frontend_image` in `terraform.tfvars`.

## Deploy

```bash
cd deployment/terraform
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform plan
terraform apply
```

## Backup Plan

- RDS automated backups are enabled with `db_backup_retention_days`.
- Final snapshots are required because `skip_final_snapshot=false`.
- S3 document versioning is enabled, with noncurrent versions retained for 90 days.
- CloudWatch logs are retained for `log_retention_days`.

## Health Checks

- ALB API target group: `/health/ready`
- ALB frontend target group: `/health`
- ECS API container checks `/health/ready`
- ECS frontend container checks `/health`

## Notes

- This stack uses private ECS tasks. ECR, Logs, S3, and Secrets Manager are reached through VPC endpoints.
- Provider credentials should continue to be saved through AuthClaw provider management; in AWS mode they are stored in Secrets Manager by the application.
- Add an ACM certificate ARN to enable HTTPS on the ALB.

