# AuthClaw DR Runbook

## Incident Entry Criteria

Declare regional failover when the primary region cannot serve authenticated API, gateway, and frontend health checks for 10 consecutive minutes or when a regional control-plane/data-plane incident prevents safe operation.

## Recovery Objectives

- RTO: 30 minutes.
- RPO: 15 minutes.
- Data sources: PostgreSQL backup copy, replicated S3 document bucket, Kafka/analytics replay where available, signed audit exports.

## Failover Steps

1. Freeze production promotion and record the incident ID.
2. Run `python scripts/dr_validation.py --terraform-outputs terraform-output.json`.
3. Confirm secondary ECS, Redis, Kafka/MSK, analytics store, and Secrets Manager values are healthy.
4. Restore PostgreSQL from the latest secondary backup copy when primary writes are unavailable.
5. Promote the secondary deployment by setting Route53 primary weight to `0` or marking the primary health check unhealthy.
6. Run frontend/backend smoke checks: `/health/ready`, `/openapi.json`, `/metrics`, login, provider test, policy simulate, approval queue, audit verify, Trust Center.
7. Record RTO/RPO evidence and publish the operational update.

## Failback Steps

1. Keep the recovered primary in read-only validation until data parity is confirmed.
2. Compare latest audit hash-chain roots and signed export manifests.
3. Run tenant isolation, approval/MFA, provider credential isolation, and gateway smoke tests.
4. Restore balanced Route53 weights only after both regions pass validation.

## Evidence Required

- Incident timeline.
- Terraform output snapshot.
- DR validation report.
- Backup recovery point ID.
- Route53 change ID.
- Smoke-test evidence.
- Audit verification report.
