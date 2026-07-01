# Phase 2 - Mandatory Streaming Redaction

Streaming redaction now lives inside the dedicated Go Gateway. It is always on
for gateway runtime streaming responses and is not controlled by any bypass
environment flag.

Runtime path:

```text
Client
  -> Go Gateway
  -> Python Governance Backend
  -> Provider Stream
  -> Go Gateway Streaming Redaction
  -> Client
```

The Python backend and provider code remain unchanged. The Go gateway wraps
streaming or chunked gateway responses before any bytes are sent to the client.

Protected runtime paths:

- `/gateway/chat`
- `/api/gateway/chat`
- `/chat`
- `/v1/chat/completions`
- `/gateway/documents/*`
- `/api/gateway/documents/*`

The redactor masks:

- API keys
- JWTs
- bearer tokens
- AWS access keys
- SendGrid keys
- Google API keys
- AuthClaw tenant API keys
- email addresses
- phone numbers
- internal system/developer prompts
- hidden policy metadata

Fragmentation safety:

The redactor keeps a bounded rolling carry buffer so secrets split across
network chunks are not flushed raw before the next chunk arrives. It does not
wait for the whole response.

Fail-closed behavior:

If redaction fails, the Go gateway closes the upstream body and emits a safe
placeholder instead of bypassing redaction.

Observability:

The gateway logs stream start, stream end, chunks processed, redaction count,
failure count, and trigger categories. It never logs raw sensitive values.
