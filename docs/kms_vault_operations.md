# KMS And Vault Operations

## AWS KMS / Secrets Manager

- ECS tasks must set `AWS_SECRETS_MANAGER_ENABLED=true`.
- Provider credentials, JWT secrets, SMTP secrets, and encryption keys are injected from Secrets Manager.
- Use customer-managed KMS keys for production secret encryption where tenant policy requires it.

## HashiCorp Vault

- Configure `VAULT_ADDR` and `VAULT_TOKEN` only for backend/gateway runtime services.
- Use short-lived Vault tokens with policy scoped to AuthClaw secret paths.
- Rotate Vault tokens through the deployment pipeline rather than the console.

## Rotation Evidence

Credential rotation must record:

- Tenant ID.
- Actor.
- Credential type.
- Previous credential version reference.
- New credential version reference.
- Audit hash-chain reference.
