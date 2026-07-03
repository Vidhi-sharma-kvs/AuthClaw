import uuid

from fastapi.testclient import TestClient

from main import API_KEY, app


client = TestClient(app)
headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def test_gateway_runs_policy_risk_provider_checks_and_audit_flow():
    session_id = f"flow-{uuid.uuid4().hex}"

    res = client.post(
        "/chat",
        headers=headers,
        json={
            "session_id": session_id,
            "message": "What is GDPR?"
        }
    )

    assert res.status_code == 200
    data = res.json()
    assert "response" in data

    trace_agents = [entry["agent"] for entry in data["trace"]]
    for expected_agent in [
        "Gateway Agent",
        "Policy Agent",
        "Risk Agent",
        "LLM Provider",
        "AuthClaw Checks",
        "Audit Agent",
    ]:
        assert expected_agent in trace_agents

    assert trace_agents.index("LLM Provider") < trace_agents.index("AuthClaw Checks")
    assert trace_agents.index("AuthClaw Checks") < trace_agents.index("Audit Agent")

    assert trace_agents.index("Security Agent") < trace_agents.index("Policy Agent")
    assert trace_agents.index("Policy Agent") < trace_agents.index("LLM Provider")
    assert trace_agents.index("LLM Provider") < trace_agents.index("Audit Agent")
