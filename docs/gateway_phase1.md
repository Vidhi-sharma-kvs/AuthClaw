# AuthClaw Gateway Phase 1

Phase 1 introduces the canonical gateway entrypoint without removing or replacing existing routes.

## Endpoint

`POST /gateway/chat`

Request body:

```json
{
  "session_id": "external-app-session-id",
  "message": "What is GDPR?"
}
```

Authentication remains compatible with existing tenant resolution:

- `X-API-Key: <tenant api key>`
- or `Authorization: Bearer <tenant api key or dashboard JWT>`

Response body:

```json
{
  "request_id": "req-...",
  "response": "...",
  "risk_level": "LOW",
  "trace": []
}
```

Blocked and approval-required responses keep the existing AuthClaw response shape and add `request_id`.

## Request Lifecycle

`/gateway/chat` uses the existing LangGraph runtime:

1. Resolve tenant from API key or JWT.
2. Generate a gateway `request_id`.
3. Set request context for runtime trace events.
4. Invoke the existing LangGraph graph.
5. Persist a row in `gateway_requests`.
6. Load real runtime events from `agent_events`.
7. Return the governed response to the caller.

## Request ID Flow

The generated `request_id` is passed into the LangGraph state and is also stored in a request-scoped context used by `log_agent_event`.

This lets existing nodes keep their current logging calls while new `agent_events` rows receive:

- `request_id`
- `sequence`
- `event_type`

`gateway_requests.created_at` records when the gateway request was registered.

## Backward Compatibility

The following routes remain active:

- `POST /chat`
- `POST /v1/chat/completions`

No dashboard pages, routes, database tables, tests, RAG flows, approval flows, or audit-chain behavior are removed in Phase 1.
