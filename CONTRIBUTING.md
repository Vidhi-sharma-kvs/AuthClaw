# Contributing to AuthClaw

AuthClaw is a gateway-first governance platform. Changes should preserve backward compatibility and avoid bypassing the Go Gateway, tenant isolation, policy enforcement, streaming redaction, and audit pipeline.

## Development Rules

- Keep changes small and scoped.
- Do not remove existing API routes or UI pages without a documented migration.
- Do not commit secrets, generated files, virtual environments, caches, logs, or PEM keys.
- Add or update tests for behavior changes.
- Prefer existing services, routers, and helpers before introducing new abstractions.

## Before Opening a PR

Run the same checks used by CI where possible:

```powershell
python -m pytest -q
cd gateway-go
go test ./...
cd ..\frontend
npm run lint
npm run build
```

For deployment changes, also run:

```powershell
cd deployment\terraform
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
```

## Pull Request Expectations

Every PR should describe:

- What changed.
- Why it changed.
- How it was tested.
- Any migration, environment, deployment, or security impact.

