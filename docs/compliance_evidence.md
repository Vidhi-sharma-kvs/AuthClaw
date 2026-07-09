# Compliance Evidence Documentation

## Evidence Sources

AuthClaw maps the following records to framework controls:

- Gateway request events.
- Policy evaluations and promotions.
- Approval lifecycle events.
- Remediation findings and execution evidence.
- Signed audit exports.
- Uploaded governance documents and RAG corpus versions.

## Auditor Workflow

1. Select framework scope: SOC2, GDPR, or HIPAA.
2. Review control-level score, evidence count, source events, and score-change reasons.
3. Export evidence by control or framework.
4. Verify the signed package before accepting it as audit evidence.

## Evidence Quality Rules

- Evidence must include tenant ID and source timestamp.
- Score changes must include reason, source event, and actor where available.
- Deleted or superseded evidence remains traceable through the audit hash chain.
