# Provider Setup

## OpenAI

- Store the API key in AuthClaw provider credentials.
- Test the connection with `POST /providers/openai/test`.
- Rotate credentials with `POST /providers/openai/rotate`.

## Anthropic

- Store the Anthropic API key in provider credentials.
- Verify that the model configured for the tenant exists in Anthropic.
- Run the provider health endpoint before sending production traffic.

## Cohere

- Store the Cohere API key in provider credentials.
- Validate native request/response compatibility with the provider test endpoint.
- Confirm fallback semantics before enabling Cohere as a failover provider.

## Azure OpenAI

- Store endpoint, deployment, API version, and credential fields in the provider credential schema.
- Use the tenant-specific Azure deployment name rather than a generic model name.
- Test routing from the console and SDK before production use.

## Operational Requirements

- Never place provider keys in frontend code.
- Rotate keys through AuthClaw so audit history records the lifecycle.
- Require Secrets Manager, KMS, or Vault-backed storage in production.
