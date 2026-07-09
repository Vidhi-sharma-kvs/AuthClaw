# Signed Export Verification

## Export

Auditor packages are available from:

- `GET /auditor/package/export`
- `GET /audit/export/package`

Each package includes a manifest with tenant, timeframe, hash-chain root, signing key ID, framework scope, payload hash, and signature.

## Verification

Use the backend verifier:

```bash
curl -X POST https://<authclaw-host>/audit/export/verify \
  -H "Authorization: Bearer <api-key>" \
  -H "Content-Type: application/json" \
  --data @auditor-package.json
```

A tampered payload, manifest, signature, tenant, timeframe, or hash-chain root must fail verification.

## Public Trust Center

The Trust Center consumes the same signed state via `GET /trust/public`. Public verification should compare the published state against the exported manifest.
