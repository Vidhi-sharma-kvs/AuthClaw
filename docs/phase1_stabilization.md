# Phase 1 Stabilization

This phase keeps the existing backend gateway, authentication, audit, policy, provider, approval, and UI routes intact. It only tightens the local product flow so tenant users land on the gateway-first experience.

## What Changed

- Tenant users who hit a route they cannot access are returned to `/chat`, the Gateway Chat page, instead of the legacy dashboard route.
- Platform administrators still return to `/platform/dashboard`.
- Login page copy now describes AuthClaw as an AI Security Gateway and no longer suggests legacy username-style sign-in.

## Why

AuthClaw is intended to be used as a governance gateway between customer applications and LLM providers. Tenant users should therefore recover to the gateway surface, not a dashboard-first page. The login copy should also guide users toward production tenant accounts, not development or legacy identities.

## Compatibility

No routes were removed. The following routes remain available for compatibility:

- `/dashboard`
- `/chat`
- `/gateway/chat`
- `/gateway/requests`
- `/gateway/approvals`
- `/platform/dashboard`

No backend API contracts, database tables, providers, audit flows, approval flows, or policy behavior were changed.

## Local Verification

Frontend:

```powershell
cd frontend
npm run build
```

Expected local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Backend health: `http://127.0.0.1:8000/health/ready`

