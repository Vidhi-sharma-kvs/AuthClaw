# Next.js Migration Assessment

## Current Architecture

AuthClaw currently uses a React/Vite console in `frontend/` with route-level protection, Axios-backed API services, and a browser E2E suite pointed at the real running application. The backend is a FastAPI service with separate Go gateway components, Terraform infrastructure, policy services, document intelligence, Trust Center APIs, provider integrations, approval flows, and audit/evidence modules.

## Migration Complexity

Estimated complexity: Medium to Large.

The UI is already structured as a routed authenticated console, which maps cleanly to a Next.js app-router or pages-router migration. The main complexity is not rendering; it is preserving existing authentication behavior, token handling, protected-route semantics, API base URL handling, and E2E coverage without changing the backend API contract.

## Risk Analysis

- Authentication/session regression risk is high if route guards, token storage, redirects, or refresh handling are changed during migration.
- Build and deployment behavior would change from static Vite assets to a Next.js runtime or static export, which affects Docker, CI, hosting, and CSP assumptions.
- Hydration and server/client component boundaries could introduce state bugs in pages that currently assume a purely client-side runtime.
- Existing Playwright tests would need route and timing review but should remain reusable as real-app checks.

## Estimated Effort

- Assessment and routing design: 2-3 days.
- Shell migration and build pipeline: 3-5 days.
- Page-by-page migration and visual parity: 1-2 weeks.
- Auth, provider, approval, document, evidence, and Trust Center regression testing: 1 week.
- Deployment and CI update: 2-4 days.

Total: approximately 3-5 engineering weeks depending on required visual parity and deployment model.

## Benefits

- Better future support for server-side rendering or static generation of public pages such as the Trust Center.
- Built-in routing conventions and framework-supported optimization.
- Easier split between public marketing/trust pages and authenticated console if the product grows in that direction.

## Reasons To Postpone

- The current Vite console is functional and already integrated with the existing backend and E2E setup.
- The SRS gaps are primarily backend governance, compliance, observability, security, and deployment validation gaps rather than frontend framework gaps.
- Migrating now would introduce avoidable regression risk in auth and protected enterprise workflows.

## Recommendation

Postpone migration until production readiness gaps are closed and the frontend API contract is stable. If migration is later approved, perform it as a dedicated compatibility project with route-by-route Playwright parity checks.
