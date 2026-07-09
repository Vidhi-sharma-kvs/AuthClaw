import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "gateway_benchmark.py"
spec = importlib.util.spec_from_file_location("gateway_benchmark", MODULE_PATH)
gateway_benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway_benchmark)


def test_percentile_interpolates_values():
    values = [100, 200, 300, 400]

    assert gateway_benchmark.percentile(values, 50) == 250
    assert gateway_benchmark.percentile(values, 95) == 385


def test_summarize_reports_success_rate_latency_and_status_codes():
    results = [
        gateway_benchmark.BenchmarkResult("/gateway/chat", 200, 100.0, True, "req-1"),
        gateway_benchmark.BenchmarkResult("/gateway/chat", 200, 200.0, True, "req-2"),
        gateway_benchmark.BenchmarkResult("/gateway/chat", 503, 300.0, False, error="provider unavailable"),
    ]

    summary = gateway_benchmark.summarize(results)

    assert summary["total_requests"] == 3
    assert summary["successes"] == 2
    assert summary["failures"] == 1
    assert summary["success_rate"] == 0.6667
    assert summary["latency_ms"]["avg"] == 150.0
    assert summary["latency_ms"]["p50"] == 150.0
    assert summary["status_codes"] == {"200": 2, "503": 1}


def test_build_headers_prefers_bearer_over_api_key():
    headers = gateway_benchmark.build_headers("ac_example", "jwt-token")

    assert headers["Authorization"] == "Bearer jwt-token"
    assert "X-API-Key" not in headers
    assert headers["Content-Type"] == "application/json"


def test_build_headers_uses_api_key_when_bearer_missing():
    headers = gateway_benchmark.build_headers("ac_example", None)

    assert headers["X-API-Key"] == "ac_example"
    assert "Authorization" not in headers


def test_evaluate_thresholds_enforces_overhead_target():
    report = {
        "summary": {"success_rate": 1.0, "latency_ms": {"p95": 120.0}},
        "overhead_ms": {"max_p95_overhead_ms": 49.0},
    }

    passed = gateway_benchmark.evaluate_thresholds(report, min_success_rate=0.99, max_p95_ms=500, max_overhead_ms=50)
    assert passed["passed"] is True

    failed = gateway_benchmark.evaluate_thresholds(
        {**report, "overhead_ms": {"max_p95_overhead_ms": 51.0}},
        min_success_rate=0.99,
        max_p95_ms=500,
        max_overhead_ms=50,
    )
    assert failed["passed"] is False
    assert failed["violations"][0]["metric"] == "max_p95_overhead_ms"
