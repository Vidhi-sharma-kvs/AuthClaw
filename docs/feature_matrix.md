# AuthClaw Feature Matrix

| Feature | Backend | Frontend | Tests | Notes |
| --- | --- | --- | --- | --- |
| Authentication / registration / verification | Implemented | Implemented | Existing auth/onboarding tests + Playwright harness | SMTP must be configured for real production email |
| MFA / TOTP / sessions | Implemented | Implemented | Existing auth and approval tests | No auth flow changes in this pass |
| RBAC | Implemented for code scope | Existing protected routes | RBAC matrix tests | Production enforcement via `AUTHCLAW_ENV=production` or `AUTHCLAW_ENABLE_RBAC_ENFORCEMENT=true` |
| Provider gateway | Implemented | Implemented | Provider/router/gateway tests | Live provider keys required for production calls |
| Trust Center | Implemented | Implemented | Trust runtime tests | Public claims depend on live deployment evidence |
| Tenant isolation | Implemented logical isolation | N/A | Tenant isolation report tests | Physical isolation out of scope |
| KMS/Vault | Implemented code paths | Admin health endpoint | Readiness tests | Live KMS/Vault required for production validation |
| DR/Terraform | Implemented code/config | N/A | Config readiness tests | Real failover drill required outside code |
| Playwright E2E | Real-app harness | Real app | Requires runtime credentials | No mocked APIs |
