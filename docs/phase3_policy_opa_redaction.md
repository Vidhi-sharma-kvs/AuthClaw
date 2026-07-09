# Phase 3 Policy, OPA, And Redaction Hardening

AuthClaw treats `policies.yaml` as the source document for baseline policy controls. The loader validates required keyword lists, redaction actions, sensitive-data actions, approval settings, and OPA metadata before the application starts.

## OPA Enforcement

Production deployments must set:

- `AUTHCLAW_OPA_ENABLED=true`
- `AUTHCLAW_OPA_POLICY_URL=http://<opa-host>:8181/v1/data/authclaw/policy`

`AUTHCLAW_ENV=production` or `AUTHCLAW_OPA_REQUIRED=true` makes OPA fail closed. If OPA is disabled, unavailable, or circuit-open in required mode, AuthClaw returns a blocking policy decision instead of falling back to local policy evaluation.

## Bundle Lifecycle

The YAML-to-OPA lifecycle is:

1. Validate `policies.yaml` with `startup.validation.load_and_validate_policy`.
2. Generate deterministic Rego with `policy.compile_policy_to_rego`.
3. Build bundle contents with `policy.build_opa_bundle`.
4. Publish `.manifest` and `authclaw.rego` to the OPA bundle source used by the deployment.
5. Promote policy versions only after lifecycle validation passes.
6. Roll back only to versions that still pass lifecycle validation.

The generated Rego covers blocked keywords, high-risk approval keywords, prompt-injection, security-bypass, data-exfiltration, secrets, PII, PHI, and financial identifiers.

## Streaming Redaction

The Go gateway removes `Accept-Encoding` before upstream proxying so streaming redaction receives inspectable response bodies. If an upstream response is still encoded or compressed, the gateway fails closed because it cannot safely inspect the stream.

Streaming redaction maintains a carry window across chunks and masks provider secrets, generic secret assignments, bearer/JWT values, email, phone, SSN, financial identifiers, medical identifiers, PHI context, prompt-injection text, internal prompts, and hidden metadata. Tests cover adversarial fragmentation where sensitive values arrive one byte at a time.
