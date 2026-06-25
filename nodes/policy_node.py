from services.policy_agent import PolicyAgent
from verify_audit import log_agent_event
import time

def policy_node(state):
    print("[Policy Start] (Policy Agent)", flush=True)
    start_time = time.perf_counter()

    message = state["message"]
    tenant_id = state.get("tenant_id", 1)
    session_id = state.get("session_id", "default")
    username = state.get("username", "admin_user")

    # If original_query is not set, set it now
    if not state.get("original_query"):
        state["original_query"] = message

    if "triggered_policies" not in state or state["triggered_policies"] is None:
        state["triggered_policies"] = []

    result = PolicyAgent().evaluate(message, username=username, tenant_id=tenant_id)
    
    log_agent_event(
        tenant_id=tenant_id,
        session_id=session_id,
        agent_name="Policy Agent",
        event_type="JAILBREAK_DETECTION_CHECK",
        details="Jailbreak and prompt injection patterns evaluated. Status: Pass."
    )

    if not result.approved and result.category:
        state["triggered_policies"].extend(result.violated_policies)
        state["allowed"] = False
        state["block_reason"] = result.reason
        state["block_category"] = result.category
        state["policy_decision"] = result.policy_decision
        print(f"POLICY NODE [BLOCKED]: {result.category} - {result.reason}")
        
        log_agent_event(
            tenant_id=tenant_id,
            session_id=session_id,
            agent_name="Policy Agent",
            event_type="POLICY_EVALUATED",
            details=f"Prompt blocked due to policy violation: {result.category} (Reason: {result.reason})."
        )
        
        duration = time.perf_counter() - start_time
        print(f"[Policy End] Duration: {duration:.4f}s", flush=True)
        return state

    allowed = result.approved
    state["triggered_policies"].extend(result.violated_policies)
    print("POLICY NODE:", allowed, state["triggered_policies"])

    state["allowed"] = allowed
    state["policy_decision"] = result.policy_decision
    
    status_str = "Allowed" if allowed else "Blocked"
    log_agent_event(
        tenant_id=tenant_id,
        session_id=session_id,
        agent_name="Policy Agent",
        event_type="POLICY_EVALUATED",
        details=f"Compliance check completed. Policy Action: {status_str}."
    )

    duration = time.perf_counter() - start_time
    print(f"[Policy End] Duration: {duration:.4f}s", flush=True)
    return state
