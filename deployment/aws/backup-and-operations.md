# AuthClaw Backup and Operations Plan

## Backups

- RDS automated backups: enabled by Terraform with `db_backup_retention_days`.
- RDS final snapshot: required on destroy because `skip_final_snapshot=false`.
- S3 document bucket: versioning enabled and encrypted at rest.
- S3 lifecycle: noncurrent document versions expire after 90 days.
- Secrets Manager: runtime secrets are stored as managed secret versions; rotate provider credentials through AuthClaw provider management.

## Log Rotation and Retention

- ECS logs go to CloudWatch log groups:
  - `/ecs/authclaw-production/api`
  - `/ecs/authclaw-production/frontend`
- Log retention is controlled by Terraform variable `log_retention_days`.
- Local EC2/systemd deployments should install `deployment/ec2/logrotate-authclaw` to rotate `/opt/authclaw/logs/*.log`.

## Health Checks

- Public frontend health: `GET /health`
- API readiness: `GET /health/ready`
- ALB target group checks:
  - frontend `/health`
  - backend `/health/ready`
- ECS container checks mirror the same endpoints.

## Recovery Checklist

1. Check ALB target health.
2. Check ECS task events and CloudWatch logs.
3. Check `/health/ready` production validation errors.
4. Check RDS status and latest automated backup.
5. Check Secrets Manager secret versions.
6. If document processing fails, confirm `AUTHCLAW_DOCUMENT_STORAGE_BACKEND=s3`, bucket policy, and task role S3 permissions.

