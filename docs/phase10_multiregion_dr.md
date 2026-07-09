# Phase 10 Multi-Region, DR, And Production Deployment

## Topology

AuthClaw uses one independently deployable Terraform stack per region. Each regional stack contains the API, Go gateway, frontend, ALB, ECS service, RDS PostgreSQL, document bucket, Redis, Kafka/MSK, analytics storage, CloudWatch logs, and secrets baseline. The same immutable container images are promoted to staging and then production regions.

When `enable_multi_region_dr=true`, the stack adds:

- Route53 weighted active-active records for the global AuthClaw hostname.
- Route53 health checks for primary and secondary regional endpoints.
- Secondary-region document bucket with S3 versioning and replication.
- AWS Backup vaults with cross-region copy for RDS and document storage recovery points.
- Terraform outputs for RTO, RPO, global URL, replica bucket, and backup vaults.

## Database Strategy

Production PostgreSQL remains the system of record per tenant. The Phase 10 DR model uses backup-copy recovery points and controlled regional promotion rather than implicit split-brain writes. A secondary region can serve read-only readiness checks and be promoted during an incident after the latest validated recovery point is restored.

Target objectives:

- RTO: 30 minutes.
- RPO: 15 minutes.
- DNS health-check interval: 30 seconds.
- Backup-copy retention: 35 days by default.

## Failover Validation

Use the validation harness after deployment:

```bash
terraform -chdir=deployment/terraform output -json > terraform-output.json
python scripts/dr_validation.py --terraform-outputs terraform-output.json
```

For CI/static validation:

```bash
python scripts/dr_validation.py --static-only
```

## Chaos Scenarios

The release readiness checklist requires evidence for:

- Mark primary Route53 health check unhealthy and verify global DNS resolves to the secondary endpoint.
- Scale the primary ECS service to zero and verify health checks fail within the RTO window.
- Block primary provider egress and verify queue/dead-letter telemetry remains visible.
- Restore PostgreSQL from the secondary backup vault and run tenant-isolation smoke tests.
- Deny primary bucket access and verify replicated document object availability in the secondary bucket.

## Promotion Control

Production promotion is gated by the dedicated promotion workflow. It requires a staging environment name, production environment approval, test result retention, immutable image tag input, and DR validation before production rollout.
