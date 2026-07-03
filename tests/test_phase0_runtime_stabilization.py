import os


def test_document_alert_respects_email_delivery_bypass(monkeypatch, tmp_path):
    from document_processing import alerts

    alerts_path = tmp_path / "alerts.log"
    monkeypatch.setattr(alerts, "ALERTS_LOG", str(alerts_path))
    monkeypatch.setenv("SKIP_EMAIL_DELIVERY_FOR_TESTING", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.invalid")
    monkeypatch.setenv("SMTP_FROM", "no-reply@example.invalid")

    alerts.trigger_security_alert(
        {
            "finding_type": "Secret",
            "risk_level": "CRITICAL",
            "matched_pattern": "API_KEY",
            "matched_text": "secret-value",
            "recommendation": "Rotate the key.",
            "impact": "Credential exposure.",
            "priority": "P1",
            "location_evidence": "Line 1",
        },
        "sample.txt",
    )

    assert alerts_path.exists()
    assert "sample.txt" in alerts_path.read_text(encoding="utf-8")


def test_remote_embeddings_can_be_disabled(monkeypatch):
    import rag.embeddings as embeddings

    monkeypatch.setenv("AUTHCLAW_DISABLE_REMOTE_EMBEDDINGS", "true")
    monkeypatch.setenv("GOOGLE_API_KEY", "real-looking-key")

    def fail_post(*args, **kwargs):
        raise AssertionError("Remote embeddings should not be called when disabled.")

    monkeypatch.setattr(embeddings.requests, "post", fail_post)

    vector = embeddings.generate_embedding("AuthClaw gateway redacts PII")
    assert len(vector) == 768
    assert any(value != 0 for value in vector)


def test_background_monitor_can_be_disabled(monkeypatch, caplog):
    import main

    monkeypatch.setenv("AUTHCLAW_DISABLE_BACKGROUND_MONITOR", "true")
    assert main.env_bool("AUTHCLAW_DISABLE_BACKGROUND_MONITOR") is True


def test_llm_node_provider_failure_uses_offline_fallback(monkeypatch):
    from nodes import llm_node as llm_module

    monkeypatch.setattr(llm_module, "get_history", lambda session_id: [])
    monkeypatch.setattr(llm_module, "log_agent_event", lambda **kwargs: None)

    def unavailable_provider():
        raise ValueError("Provider not configured")

    monkeypatch.setattr(llm_module, "get_provider", unavailable_provider)

    result = llm_module.llm_node(
        {
            "allowed": True,
            "message": "hello",
            "session_id": "phase0-test",
            "tenant_id": 1,
        }
    )

    assert result["provider_status"] == "offline_fallback"
    assert result["response"].startswith("[Offline Fallback]")


def test_email_delivery_soft_fail_is_local_only(monkeypatch):
    import main

    monkeypatch.setenv("AUTHCLAW_ENV", "development")
    monkeypatch.setenv("AUTHCLAW_SOFT_FAIL_EMAIL_DELIVERY", "true")
    assert main.soft_fail_email_delivery_for_local() is True

    monkeypatch.setenv("AUTHCLAW_ENV", "production")
    assert main.soft_fail_email_delivery_for_local() is False
