# OIDC Setup

## Tenant IdP Configuration

1. Register AuthClaw as an OIDC client in the enterprise IdP.
2. Configure redirect URI: `https://<authclaw-host>/auth/oidc/callback`.
3. Store issuer, client ID, client secret, and allowed domains in AuthClaw identity provider configuration.
4. Enable the provider only after JWKS discovery succeeds.

## Required Claims

- `sub`: stable user identifier.
- `email`: user email.
- `email_verified`: required for production login.
- Group or role claim mapped into tenant RBAC policy.

## Validation

- Login creates a tenant-scoped user session.
- Disabled IdP configuration rejects new login attempts.
- JWKS cache refresh does not bypass tenant isolation.
- Audit logs include login, logout, and IdP configuration changes.
