# Phase 1 Core Security And Tenant Foundation

Phase 1 adds enterprise identity and security hardening while preserving the existing AuthClaw username/password, JWT, MFA, API key, provider, document intelligence, and Go gateway behavior.

## Scope Implemented

- Additive tenant-level OIDC/SSO configuration.
- OIDC Authorization Code Flow with PKCE.
- OIDC callback that issues existing AuthClaw access and refresh tokens.
- Encrypted tenant IdP client secret storage.
- JWKS refresh/cache support for external RS256 ID token validation.
- Safe stale JWKS fallback during temporary IdP key refresh failures.
- Provider refresh token encryption and storage.
- Logout endpoint that revokes AuthClaw refresh tokens.
- Public JWKS metadata endpoint for current session-key posture.
- Production HTTPS redirect/HSTS/security-header middleware.
- Production disabling for local email/domain verification bypass flags.
- Explicit secret backend selection policy for local, AWS Secrets Manager/KMS envelope use, and HashiCorp Vault.
- RLS policies for all new tenant-scoped identity tables.
- Phase 1 regression tests for PKCE, HTTPS, bypass handling, IdP config encryption, OIDC login state, and RLS policy presence.

## Preserved Backward Compatibility

- `/auth/login` is unchanged.
- `/auth/verify-otp` is unchanged.
- Existing HS256 AuthClaw session JWTs are unchanged.
- Existing refresh token records remain compatible.
- Existing tenant API key authentication remains compatible.
- Provider routing and provider integrations are unchanged.
- Go gateway routing is unchanged.
- Document intelligence modules are unchanged.

## New Endpoints

| Method | Path | Purpose | Auth |
| --- | --- | --- | --- |
| `GET` | `/.well-known/jwks.json` | Public session-key posture metadata | Public |
| `GET` | `/auth/jwks` | Same JWKS metadata for clients that prefer auth path | Public |
| `GET` | `/auth/oidc/providers` | List enabled tenant IdPs by `tenant_id` or `domain` | Public |
| `GET` | `/auth/oidc/login` | Create OIDC authorization URL with PKCE state | Public |
| `GET` | `/auth/oidc/callback` | Complete OIDC callback from query params | Public |
| `POST` | `/auth/oidc/callback` | Complete OIDC callback from JSON body | Public |
| `POST` | `/auth/logout` | Revoke AuthClaw refresh token if supplied | Public |
| `GET` | `/identity/providers` | List tenant IdP configs without secrets | Super Admin or Security Admin |
| `POST` | `/identity/providers` | Create/update tenant IdP config | Super Admin or Security Admin |
| `POST` | `/identity/providers/{provider_id}/enabled` | Enable/disable tenant IdP | Super Admin or Security Admin |
| `GET` | `/security/posture` | Tenant security posture summary | Super Admin or Security Admin |

## Tenant IdP Configuration

Each tenant can configure:

- Provider type: Microsoft Entra ID, Google Workspace, Okta, Auth0, or Generic OIDC.
- Client ID.
- Client secret.
- Discovery URL.
- Issuer.
- Authorization endpoint.
- Token endpoint.
- UserInfo endpoint.
- JWKS URI.
- Redirect URI.
- Scopes.
- Groups claim.
- Group-to-role mapping.
- Enabled/disabled state.

Client secrets are encrypted through `SecretManager.encrypt_for_database` before persistence and are never returned by list APIs.

## RLS Coverage

The following new tenant-scoped tables have RLS enabled and forced:

- `tenant_identity_providers`
- `oidc_login_states`
- `oidc_jwks_cache`
- `oidc_user_sessions`

`tenant_identity_providers`, `oidc_login_states`, and `oidc_jwks_cache` permit `auth_lookup_context` reads where required by public OIDC login/callback flows. Writes remain tenant-scoped.

## Secret Backend Policy

`SecretManager` now exposes an explicit selection policy:

1. HashiCorp Vault when `VAULT_ADDR` and `VAULT_TOKEN` are present.
2. AWS Secrets Manager when explicitly enabled by `AWS_SECRETS_MANAGER_ENABLED=true`, or when `AUTHCLAW_SECRET_BACKEND=auto` and AWS region is configured.
3. Local encrypted storage for development.

Production validation continues to reject local-only secret backends.

## HTTPS Policy

Production or `AUTHCLAW_ENFORCE_HTTPS=true` enables:

- HTTP to HTTPS redirects for non-local hosts.
- HSTS.
- `X-Content-Type-Options: nosniff`.
- `X-Frame-Options: DENY`.
- `Referrer-Policy: strict-origin-when-cross-origin`.
- Secure/SameSite attributes for outgoing cookies when cookies are present.

Localhost and `127.0.0.1` HTTP remain allowed for development.

## Deferred To Later Phases

- Full UI for tenant IdP configuration.
- External IdP logout redirect orchestration.
- Asymmetric AuthClaw-issued session JWTs.
- Full route-by-route RBAC redesign.
- Removal of legacy approval MFA bypass, which belongs to Phase 4.
- Provider additions and routing changes, which belong to Phase 2.
