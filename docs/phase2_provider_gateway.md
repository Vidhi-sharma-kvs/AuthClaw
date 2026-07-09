# Phase 2 Provider Gateway Completion

Phase 2 completes the SRS-required provider gateway surface while preserving existing gateway, authentication, tenant isolation, and document intelligence behavior.

## Runtime Provider IDs

| Provider | Canonical ID | Native runtime adapter |
| --- | --- | --- |
| OpenAI | `openai` | `providers.openai_provider.OpenAIProvider` |
| Anthropic | `anthropic` | `providers.anthropic_provider.AnthropicProvider` |
| Cohere | `cohere` | `providers.cohere_provider.CohereProvider` |
| Azure OpenAI | `azure_openai` | `providers.azure_openai_provider.AzureOpenAIProvider` |

Gemini remains supported as an existing non-SRS provider under `gemini`.

## Normalized Credential Schema

All provider credential inputs are normalized before validation, storage, health checks, and routing.

Common fields:

- `api_key`
- `model`
- `api_base`
- `live_test`

Azure OpenAI fields:

- `api_base`
- `api_version`
- `deployment`

Backward-compatible aliases are accepted:

- `endpoint` or `base_url` -> `api_base`
- `azure_endpoint` -> `api_base`
- `azure_api_version` -> `api_version`
- `deployment_name` -> `deployment`

The backend accepts both the canonical nested contract:

```json
{
  "provider": "openai",
  "payload": {
    "api_key": "sk-...",
    "model": "gpt-4o"
  }
}
```

and the legacy/top-level UI-compatible shape:

```json
{
  "provider": "azure_openai",
  "api_key": "...",
  "azure_endpoint": "https://resource.openai.azure.com",
  "azure_api_version": "2024-02-15-preview",
  "deployment": "gpt-4o-production"
}
```

## Console Contract

Gateway Center now calls the existing backend contracts:

- Connect: `POST /providers/connect`
- Rotate: `POST /providers/{provider}/rotate`
- Test: `POST /providers/{provider}/test`
- Health: `GET /providers/{provider}/health`
- Delete: `DELETE /providers/{provider}`

## Native Payload Compatibility

Provider adapters emit native request formats:

- OpenAI: `POST /v1/chat/completions` with `messages`.
- Anthropic: `POST /v1/messages` with Anthropic version header.
- Cohere: `POST /v2/chat` with `messages`.
- Azure OpenAI: `POST /openai/deployments/{deployment}/chat/completions?api-version=...`.

## Fallback And Error Semantics

- Missing or invalid tenant credentials fail before provider routing with provider-specific validation errors.
- Live provider checks are opt-in. Non-live checks validate credential shape only.
- Stored raw provider secrets are never returned by connect, list, health, test, rotate, or delete APIs.
- Provider router preference order remains tenant route, tenant credential, environment secret, then legacy local fallback.
- Azure OpenAI is no longer collapsed into OpenAI; it routes through its native deployment adapter.
- Cohere is now a first-class provider in routing, validation, health checks, and the console.
