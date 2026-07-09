import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_sdk():
    module_path = ROOT / "sdk" / "python" / "authclaw_client.py"
    spec = importlib.util.spec_from_file_location("authclaw_client", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase11_sdk_exposes_production_client_contract():
    sdk = load_sdk()
    client = sdk.AuthClawClient("https://authclaw.example.test", "test-key", timeout=5, max_retries=2)

    required_methods = [
        "gateway_chat",
        "chat_completions",
        "stream_chat_completion",
        "list_providers",
        "connect_provider",
        "test_provider",
        "rotate_provider",
        "list_approvals",
        "approve",
        "execute_approval",
        "generate_api_key",
        "launch_remediation_scan",
        "export_auditor_package",
        "verify_export",
    ]
    for method in required_methods:
        assert callable(getattr(client, method))

    assert sdk.AuthClawRateLimitError
    assert sdk.AuthClawAuthenticationError
    assert sdk.GatewayChatResponse


def test_phase11_sdk_metadata_marks_stable_typed_package():
    pyproject = read("sdk/python/pyproject.toml")
    readme = read("sdk/python/README.md")

    assert 'version = "1.0.0"' in pyproject
    assert "Production/Stable" in pyproject
    assert "Typing :: Typed" in pyproject
    assert "Retries with exponential backoff" in readme
    assert "stream_chat_completion" in readme


def test_phase11_customer_docs_cover_required_operations():
    docs = "\n".join(
        read(path)
        for path in [
            "docs/phase11_sdk_developer_experience.md",
            "docs/provider_setup.md",
            "docs/oidc_setup.md",
            "docs/kms_vault_operations.md",
            "docs/export_verification.md",
            "docs/compliance_evidence.md",
            "deployment/aws/dr-runbook.md",
        ]
    )

    required = [
        "/openapi.json",
        "OpenAI",
        "Anthropic",
        "Cohere",
        "Azure OpenAI",
        "OIDC",
        "AWS KMS",
        "HashiCorp Vault",
        "Signed Export Verification",
        "Auditor Workflow",
        "RTO",
        "RPO",
    ]
    for item in required:
        assert item in docs
