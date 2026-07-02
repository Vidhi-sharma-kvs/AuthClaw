# Security Policy

AuthClaw handles tenant data, provider credentials, audit logs, redaction metadata, and gateway API keys. Treat all credentials and customer data as sensitive.

## Do Not Commit

- `.env` files
- PEM or PPK keys
- JWT secrets
- Provider API keys
- SMTP credentials
- Database credentials
- Generated deployment env files
- Local logs, caches, screenshots, or test artifacts containing customer data

## Reporting Security Issues

Please do not open public issues for exploitable vulnerabilities. Use a private disclosure channel with the repository owner and include:

- A clear description of the issue.
- Impacted component.
- Reproduction steps.
- Whether credentials or tenant data could be exposed.
- Suggested mitigation, if known.

## Required Behavior

Production deployments must fail closed when required secrets, tenant controls, policy enforcement, or audit persistence are unavailable.

