# Final Runtime Architecture

AuthClaw runtime requests now enter LangGraph through `GatewayService`. Public compatibility routes remain, but their runtime path is canonical.

## Canonical Gateway Service

- `main.py::get_gateway_service()` constructs `GatewayService(graph=graph, resolve_tenant=resolve_tenant, decode_jwt=decode_jwt)`.
- `services/gateway_service.py::execute_chat()` generates `request_id`, resolves tenant identity, sets agent trace context, invokes LangGraph, calls `RegistrarService`, reads `agent_events`, and formats execution metadata.
- `services/gateway_service.py::execute_approval()` performs the same lifecycle for approved HITL executions and emits an `Approval Execute` trace event before graph execution.

## `/gateway/chat`

Source route: `main.py::gateway_chat`

Runtime flow:

```text
Client
-> POST /gateway/chat
-> get_gateway_service()
-> GatewayService.execute_chat()
-> request_id + trace context
-> LangGraph
-> Decision Engine
-> Approval Engine
-> Provider Router
-> RAG
-> LLM
-> Response Inspection
-> Audit
-> RegistrarService
-> response
```

## `/chat`

Source route: `main.py::chat`

`/chat` is a backward-compatible route. It delegates directly to `GatewayService.execute_chat()` and returns `GatewayService.format_chat_response()`.

## `/v1/chat/completions`

Source route: `main.py::chat_completions`

The OpenAI-compatible endpoint preserves its response contract while routing execution through `GatewayService.execute_chat()`. It converts the gateway result into a `chat.completion` response shape.

## `/execute/{approval_id}`

Source route: `main.py::execute_request`

Runtime flow:

```text
Approval Center or API
-> POST /execute/{approval_id}
-> validate approval record
-> mark approval executed
-> GatewayService.execute_approval()
-> request_id + trace context
-> Approval Execute event
-> LangGraph
-> Decision Engine
-> Provider Router
-> RAG
-> LLM
-> Response Inspection
-> Audit
-> RegistrarService
-> legacy approval audit block
-> response
```

The route preserves the legacy response fields:

- `message`
- `query`
- `response`

It also returns gateway metadata:

- `request_id`
- `provider`
- `model`
- `route_id`
- `decision`
- `trace`

## Remaining Non-Canonical Code

- `resume.py::resume_approved_request()` still invokes `graph.invoke()` directly, but repository search shows no imports or callers outside `resume.py`.
- `test_graph.py` contains manual/test-only direct graph execution.
- `nodes.llm_node` can call `providers.get_provider()` only if `provider_client` is missing from graph state. Canonical runtime reaches `llm_node` after `provider_router_node`, which sets `provider_client`.

## Provider Access

Canonical provider selection is tenant-aware:

```text
Provider Router
-> services.provider_router.ProviderRouter
-> gateway_routes
-> tenant_credentials
-> provider_client
-> llm_node
```

Non-routing provider access remains in:

- startup initialization for provider readiness checks
- health details endpoint for provider health
- `llm_node` as a defensive legacy fallback
