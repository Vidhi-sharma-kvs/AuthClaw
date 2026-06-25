# Runtime Execution Analysis

This document captures the actual Phase 1 runtime path before Phase 2 refactoring.

## 1. Where `/gateway/chat` Executes

`POST /gateway/chat` is registered in `main.py` and delegates to `GatewayService`.

```text
main.py::gateway_chat
  -> get_gateway_service()
  -> GatewayService.execute_chat()
  -> resolve_tenant()
  -> graph.invoke()
  -> GatewayService.format_chat_response()
```

The service creates `request_id`, resolves `tenant_id`, sets request-scoped trace context, invokes LangGraph, writes a `gateway_requests` row, loads trace records from `agent_events`, and formats the response.

## 2. Which Node Calls the Provider

The provider call happens in `nodes/llm_node.py`.

```text
nodes/llm_node.py::llm_node
  -> providers.get_provider()
  -> provider.generate(prompt)
```

`llm_node` is reached after:

```text
orchestrator -> redact -> policy -> risk -> approval -> rag -> llm
```

Requests that are blocked by policy or pending approval do not call the provider.

## 3. Which File Selects the Provider

Provider selection currently happens in `providers/__init__.py`.

```text
providers/__init__.py::get_provider()
  -> providers.config.MODEL_PROVIDER
  -> GeminiProvider()
```

`providers/config.py` reads:

```text
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "gemini")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")
```

## 4. Whether Gemini Is Hardcoded

Gemini is effectively hardcoded as the only supported runtime provider:

- `MODEL_PROVIDER` defaults to `gemini`.
- `providers.get_provider()` only supports `"gemini"`.
- No OpenAI provider implementation exists in the current runtime.

## 5. Whether `tenant_credentials` Are Used

`tenant_credentials` are used by management routes:

```text
POST /providers/connect
GET /providers/list
DELETE /providers/{provider}
```

They are not used by the provider execution path. `llm_node` still calls `providers.get_provider()`, which reads environment/global configuration.

## 6. Whether `gateway_routes` Are Used

`gateway_routes` are used by management routes and dashboard metrics:

```text
GET /routes
POST /routes
PUT /routes/{route_id}
DELETE /routes/{route_id}
GET /metrics
```

They are not used by provider execution. Runtime requests do not select route, provider, or model from `gateway_routes`.

## 7. Database Tables Written During a Request

For a normal allowed request:

```text
agent_events      <- Gateway/Policy/Risk/Provider/Response/Audit trace events
gateway_requests  <- GatewayService request registration
chat_sessions     <- memory.ensure_session_exists()
chat_messages     <- assistant response and trace persistence
logs/audit.log    <- audit_node file append
```

For blocked or approval-required requests, additional writes may happen:

```text
audit_logs        <- audit_node creates cryptographic audit block
chat_messages     <- blocked/system approval card
```

Approvals are currently also stored in memory inside `approval_store.py`.

## 8. Audit Functions That Run During a Request

Runtime audit-related functions:

```text
verify_audit.log_agent_event()
verify_audit.record_gateway_request()
nodes/audit_node.audit_node()
verify_audit.create_audit_block()       # only blocked, pending, or triggered-policy requests
startup.audit.log_audit_event()         # audit chain lifecycle events
```

Normal allowed requests currently append to `logs/audit.log` and write a normal `Audit Agent` trace event, but do not always create a cryptographic `audit_logs` block. This is existing behavior and must be preserved unless intentionally changed later.

## 9. Trace Functions That Run During a Request

Trace recording is centralized through:

```text
verify_audit.set_agent_event_context(request_id)
verify_audit.log_agent_event(...)
verify_audit.clear_agent_event_context(token)
GatewayService.get_trace(...)
GatewayService.persist_latest_message_trace(...)
```

`log_agent_event` writes to `agent_events` and attaches `request_id` and `sequence` when request context is active.

## Real Execution Path Diagram

```text
External App
  |
  v
POST /gateway/chat
  |
  v
main.py::gateway_chat
  |
  v
GatewayService.execute_chat
  |
  +--> resolve_tenant()
  |
  +--> set_agent_event_context(request_id)
  |
  v
graph.invoke(state)
  |
  v
orchestrator_node
  |
  v
redact_node
  |
  v
policy_node
  |
  +--> if blocked -> audit_node -> END
  |
  v
risk_node
  |
  v
approval_node
  |
  +--> if pending approval -> audit_node -> END
  |
  v
rag_node
  |
  v
llm_node
  |
  v
providers.get_provider()
  |
  v
GeminiProvider.generate()
  |
  v
response_checks_node
  |
  v
audit_node
  |
  v
GatewayService.record_gateway_request + trace response
  |
  v
External App
```

## Phase 2 Refactor Implication

The real replacement points are:

- `providers.get_provider()` inside `llm_node` must be replaced by tenant-aware provider routing.
- decision behavior currently split between `policy_node`, `risk_node`, and `approval_node` must be centralized without changing outcomes.
- approval persistence must be added behind the existing `approval_store.py` API.
- registrar behavior should be added as a service while preserving `audit_node` and audit-chain behavior.
