# TypeScript Worker Assessment

## Current Worker Model

AuthClaw currently uses Python services and workers for compliance evidence, document intelligence, redaction, policy processing, Trust Center runtime, production readiness checks, and remediation-oriented backend workflows. This keeps worker logic close to the FastAPI service layer and existing test fixtures.

## Future TypeScript Worker Option

A future TypeScript worker runtime could be useful for browser-adjacent processing, SDK-shared schemas, queue consumers, and typed event pipelines. It would likely run as a separate Node.js service, consume Kafka/Redis queues, and call backend APIs or shared storage.

## Compatibility Considerations

- Existing Python models, migrations, services, and tests would need schema contracts before workers are split.
- Queue payloads would require versioned JSON schemas and compatibility tests.
- Secret handling, tenant isolation, audit chain writes, and approval execution must remain backend-authoritative.
- Document intelligence and provider-specific integrations should not be rewritten until queue/event contracts are stable.

## Migration Plan

1. Define event schemas for worker inputs and outputs.
2. Generate or share OpenAPI/JSON Schema contracts.
3. Add a TypeScript worker prototype for non-destructive read-only jobs only.
4. Add contract tests proving parity with Python services.
5. Move low-risk asynchronous jobs first, such as report generation or evidence packaging.
6. Keep destructive remediation and approval-bound execution in the existing backend until Phase 12 security validation is complete.

## Risk

Risk is Medium to Large. The main risk is not TypeScript itself; it is splitting security-sensitive execution across runtimes before tenant isolation, audit consistency, and queue delivery semantics are fully proven.

## Estimated Effort

- Contract and schema design: 1 week.
- Worker service scaffold and CI: 1 week.
- First non-destructive worker migration: 1-2 weeks.
- Security-sensitive worker migration: 3-6 weeks after queue and audit guarantees are production-proven.

## Recommendation

Do not rewrite workers now. Keep Python workers as the source of truth, add typed contracts, and revisit TypeScript workers after production queue/observability work is complete.
