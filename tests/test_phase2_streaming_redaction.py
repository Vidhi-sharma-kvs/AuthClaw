from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_go_gateway_enforces_streaming_redaction_in_modify_response():
    server = (ROOT / "gateway-go" / "internal" / "gateway" / "server.go").read_text()

    assert "streamRedactionRequired(resp)" in server
    assert "newRedactingReadCloser(resp.Body, resp.Request.URL.Path)" in server
    assert 'resp.Header.Set("X-AuthClaw-Streaming-Redaction", "enforced")' in server
    assert 'resp.Header.Del("Content-Length")' in server
    assert 'req.Header.Del("Accept-Encoding")' in server
    assert 'return errors.New("stream redaction cannot inspect encoded upstream response")' in server


def test_redactor_masks_required_sensitive_categories_and_fail_closes():
    redactor = (ROOT / "gateway-go" / "internal" / "gateway" / "redactor.go").read_text()
    body = (ROOT / "gateway-go" / "internal" / "gateway" / "redacting_body.go").read_text()

    for trigger in [
        "jwt",
        "aws_access_key",
        "openai_api_key",
        "sendgrid_api_key",
        "google_api_key",
        "authclaw_api_key",
        "bearer_token",
        "email",
        "phone",
        "system_prompt",
        "hidden_metadata",
    ]:
        assert f'trigger:     "{trigger}"' in redactor

    assert "streamSafePlaceholder" in redactor
    assert "failForTest" in redactor
    assert "stream_redaction_failure" in body
    assert "stream_redaction_end" in body
    assert "stream_redaction_start" in body


def test_go_streaming_redaction_tests_cover_mandatory_cases():
    redactor_test = (ROOT / "gateway-go" / "internal" / "gateway" / "redactor_test.go").read_text()
    server_test = (ROOT / "gateway-go" / "internal" / "gateway" / "server_test.go").read_text()

    assert "TestStreamingRedactorMasksSecretsEmailAndPhone" in redactor_test
    assert "TestStreamingRedactorHandlesSplitTokenAcrossChunks" in redactor_test
    assert "TestStreamingRedactorHighSpeedChunks" in redactor_test
    assert "TestStreamingRedactorFailClosedPlaceholder" in redactor_test
    assert "TestStreamingRedactorMasksInternalPromptAndMetadata" in redactor_test
    assert "TestGatewayRedactsProxiedSSEStream" in server_test
