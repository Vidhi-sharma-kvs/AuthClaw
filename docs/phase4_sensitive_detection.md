# Phase 4 - Strong PII and Secret Detection

Phase 4 upgrades AuthClaw from regex-only masking to a policy-driven sensitive data detection layer.

## What Changed

- Added `services/sensitive_data_detection.py`.
- Integrated optional Microsoft Presidio analysis when `presidio-analyzer` is installed.
- Added custom recognizers for Aadhaar, PAN, GSTIN, email, phone, credit cards, SSNs, OpenAI keys, Google API keys, AWS access keys, JWTs, bearer tokens, and generic secret assignments.
- Added policy actions: `allow`, `redact`, `block`, `require_approval`, `mask`, `hash`, and `tokenize`.
- Added salted HMAC fingerprints for hashes and token IDs.
- Sanitized finding metadata so raw secrets and identifiers are not stored in audit metadata.

## Runtime Flow

Gateway requests still enter the existing Security Agent:

```text
Gateway request
-> SecurityAgent.inspect_input()
-> redact_sensitive_data_rich()
-> SensitiveDataDetector.redact()
-> Policy Agent
-> Decision Engine
-> Provider Router, only when allowed
```

Secret findings use policy action `block`, so API keys, JWTs, AWS keys, and provider credentials stop before the provider call.

PII findings use configured redaction actions. Aadhaar and email are masked, phone values are salted-hashed, and PAN/GSTIN values are tokenized.

## Metadata Safety

Audit and trace metadata stores:

- `token_id`
- salted `value_hash`
- `confidence`
- `action`
- detector source

It does not store the original sensitive value.
