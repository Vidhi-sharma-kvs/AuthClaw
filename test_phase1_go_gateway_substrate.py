from pathlib import Path


ROOT = Path(__file__).resolve().parent


def test_go_gateway_source_exists_and_handles_gateway_paths():
    server_source = (ROOT / "gateway-go" / "internal" / "gateway" / "server.go").read_text()

    assert 'normalized == "/gateway/chat"' in server_source
    assert 'normalized == "/v1/chat/completions"' in server_source
    assert 'strings.HasPrefix(normalized, "/gateway/documents/")' in server_source
    assert 'X-AuthClaw-Gateway' in server_source
    assert 'backendPath(req.URL.Path)' in server_source
    assert "streamRedactionRequired(resp)" in server_source


def test_local_startup_requires_go_gateway():
    start_script = (ROOT / "scripts" / "start-local.ps1").read_text()

    assert "GatewayPort = 9000" in start_script
    assert "Go is mandatory for AuthClaw Phase 1" in start_script
    assert "AUTHCLAW_BACKEND_URL" in start_script
    assert "AUTHCLAW_GATEWAY_ADDR" in start_script
    assert "VITE_API_BASE_URL = \"http://127.0.0.1:$GatewayPort\"" in start_script
    assert '"run", ".\\cmd\\authclaw-gateway"' in start_script


def test_frontend_defaults_to_go_gateway_not_python_backend():
    api_source = (ROOT / "frontend" / "src" / "services" / "api.js").read_text()
    api_keys_source = (ROOT / "frontend" / "src" / "pages" / "APIKeys" / "APIKeys.jsx").read_text()

    assert "http://127.0.0.1:9000" in api_source
    assert "http://127.0.0.1:8000" not in api_source
    assert "VITE_GATEWAY_PUBLIC_URL" in api_keys_source
    assert "/gateway/chat" in api_keys_source


def test_production_compose_has_gateway_between_frontend_and_python():
    compose = (ROOT / "docker-compose.production.yml").read_text()
    nginx = (ROOT / "frontend" / "nginx" / "authclaw.conf").read_text()

    assert "authclaw-gateway:" in compose
    assert "AUTHCLAW_BACKEND_URL: http://authclaw-api:8000" in compose
    assert "9000:9000" in compose
    assert "authclaw-frontend:" in compose
    assert "authclaw-gateway" in nginx
    assert "proxy_pass http://authclaw-gateway:9000/api/;" in nginx
