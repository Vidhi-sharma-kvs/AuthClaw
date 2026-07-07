from memory import get_history
from providers import get_provider
from verify_audit import log_agent_event
import time
import concurrent.futures


def _offline_provider_fallback(error_message: str) -> str:
    return (
        "[Offline Fallback] The configured model provider is currently unavailable. "
        "AuthClaw completed the gateway security, policy, and audit checks, but the "
        "upstream LLM call could not be completed. Check the Providers page, API "
        "credentials, and outbound network access, then try again."
    )


def llm_node(state):

    print("ENTERED LLM NODE")

    # Defensive guard: never call the LLM for pending approval requests
    if state.get("approval_status") == "PENDING_APPROVAL":
        print("LLM NODE: Skipping — approval_status is PENDING_APPROVAL", flush=True)
        return state

    if not state["allowed"]:
        return {
            **state,
            "response": "Policy Violation"
        }

    context = state.get(
        "context",
        ""
    )

    session_id = state.get(
        "session_id",
        "default"
    )
    tenant_id = state.get("tenant_id", 1)

    history = get_history(
        session_id
    )

    history_text = ""

    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content")
        if content is None:
            if role == "blocked":
                category = msg.get("category", "policy_violation")
                content = f"[Blocked: {category}]"
            elif role == "system" and "approvalId" in msg:
                content = f"[Pending Approval: {msg.get('approvalId')}]"
            else:
                content = ""
        history_text += f"{role}: {content}\n"


    prompt = f"""
You are a compliance assistant.

Conversation History:
{history_text}

Compliance Context:
{context}

User Question:
{state['message']}
"""

    print("[Provider Start]", flush=True)
    start_time = time.perf_counter()

    try:
        provider = state.get("provider_client")
        if provider is None:
            provider = get_provider()
            state["provider"] = provider.__class__.__name__
            state["model"] = getattr(provider, "model_name", "authclaw-gateway")
            state["provider_route_source"] = "legacy_provider_fallback"
        
        log_agent_event(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_name="LLM Provider",
            event_type="ROUTE_SELECTED",
            details=(
                f"Selected model route: {state.get('provider')} "
                f"({state.get('model')}) via {state.get('provider_route_source')}."
            )
        )
        
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(provider.generate, prompt)
            final_response = future.result(timeout=30.0)
        except concurrent.futures.TimeoutError as te:
            print("[Provider End] Timeout occurred", flush=True)
            raise TimeoutError("Model provider generate call timed out after 30 seconds") from te
        finally:
            executor.shutdown(wait=False)
        duration = time.perf_counter() - start_time
        print(f"[Provider End] Duration: {duration:.4f}s", flush=True)
        
        log_agent_event(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_name="LLM Provider",
            event_type="PROVIDER_RESPONSE_RECEIVED",
            details="Received response successfully from upstream provider."
        )
        
    except Exception as e:
        duration = time.perf_counter() - start_time
        print(f"[Provider End] Duration: {duration:.4f}s", flush=True)
        print(f"LLM Node Provider error: {e}. Returning offline fallback response.")
        
        log_agent_event(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_name="LLM Provider",
            event_type="PROVIDER_FAILOVER",
            details=f"Primary model connection failed: {str(e)}. Falling back to offline provider response."
        )
        final_response = _offline_provider_fallback(str(e))
        state["provider_status"] = "offline_fallback"
        state["provider_error"] = str(e)

    return {
        **state,
        "response": final_response
    }
