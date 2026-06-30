# Phase 4 - OpenAI-Compatible Streaming Gateway

## What changed

Phase 4 adds streaming support to AuthClaw's OpenAI-compatible endpoint:

```http
POST /v1/chat/completions
```

When the request body includes:

```json
{
  "stream": true
}
```

AuthClaw returns a Server-Sent Events response using the OpenAI-compatible `chat.completion.chunk` shape.

## Why it matters

Many enterprise apps already use OpenAI-style streaming. This lets a customer replace direct provider calls with AuthClaw while still keeping a streaming integration pattern.

## Governance behavior

Streaming does not bypass governance. The request still executes through the canonical gateway lifecycle first:

```text
External App
-> /v1/chat/completions
-> GatewayService
-> Security Agent
-> Policy Agent
-> Decision Engine
-> Provider Router
-> LLM Provider
-> Response Inspection
-> Audit Agent
-> Registrar Agent
-> SSE response stream
```

If the request is blocked or requires approval, AuthClaw returns the existing non-streaming policy/approval response instead of streaming unsafe output.

## Compatibility

Non-streaming behavior is unchanged. Existing requests with `"stream": false` or no `stream` field still receive the normal JSON response.

## Current scope

The first streaming implementation streams the governed, inspected final response as OpenAI-compatible SSE chunks. It does not yet proxy token-by-token provider streams directly from upstream providers. This keeps audit and response inspection intact while adding client streaming compatibility.
