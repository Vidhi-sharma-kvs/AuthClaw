from pathlib import Path

import importlib.util


ROOT = Path(__file__).resolve().parent


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_phase12_ci_workflow_contains_release_safety_gates():
    workflow = read(".github/workflows/ci.yml")

    required = [
        "backend-tests:",
        "frontend-quality:",
        "security-scan:",
        "docker-build:",
        "terraform-validate:",
        "live-benchmark:",
        "pytest -q",
        "npm run lint",
        "npm run build",
        "bandit -r",
        "npm audit --audit-level=high",
        "docker build -t authclaw-api:ci",
        "docker build -t authclaw-frontend:ci",
        "terraform validate",
        "scripts/gateway_benchmark.py",
    ]

    for item in required:
        assert item in workflow


def test_phase12_required_quality_test_suites_exist():
    required_tests = [
        "test_gateway_chat.py",
        "test_gateway_lifecycle.py",
        "test_gateway_document_redaction.py",
        "test_document_intelligence.py",
        "test_tenant_isolation_hardening.py",
        "test_tenant_route_isolation.py",
        "test_auth_backend.py",
        "test_phase8_approval_workflow.py",
        "test_provider_router.py",
        "test_gateway_benchmark.py",
    ]

    for filename in required_tests:
        assert (ROOT / filename).exists(), f"Missing required suite: {filename}"


def test_phase12_load_test_uses_gateway_benchmark_and_enforces_thresholds():
    script = read("scripts/load_test.py")

    assert "run_benchmark" in script
    assert "--min-success-rate" in script
    assert "--max-p95-ms" in script
    assert "load-test-report.json" in script

    module_path = ROOT / "scripts" / "load_test.py"
    spec = importlib.util.spec_from_file_location("load_test", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.main)


def test_phase12_scope_document_names_mvp_boundaries():
    scope = read("docs/phase12_ci_quality.md")

    assert "Upload PDF/image" in scope
    assert "Detect PII and secrets" in scope
    assert "Generate redacted text/PDF" in scope
    assert "Document chat and RAG should remain secondary" in scope

