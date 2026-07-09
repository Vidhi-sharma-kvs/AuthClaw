# AuthClaw Trust Center Guide

The Trust Center is available at `/trust` in the console and consumes signed public state from `/trust/public`.

Runtime health is available at:

```text
GET /trust/public/health
```

The public state includes:

- signed export manifest
- hash-chain root
- framework scores
- audit-chain status
- provider credential health summary
- certificate/public URL status
- event pipeline metrics
- verification endpoint metadata

The route is cached with `AUTHCLAW_TRUST_CENTER_CACHE_SECONDS` to avoid timeout-prone recomputation. The default cache is 60 seconds.

Production public claims require real deployment configuration: HTTPS public URL, certificate, provider credentials, customer evidence, and auditor-approved control mappings.
