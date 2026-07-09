import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "performance_validation.py"
spec = importlib.util.spec_from_file_location("performance_validation", MODULE_PATH)
performance_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(performance_validation)


class Thresholds:
    max_streaming_ms = 5000.0
    max_document_scan_ms = 5000.0
    max_vector_search_ms = 5000.0


def test_phase9_local_performance_report_passes_thresholds():
    report = performance_validation.build_report()
    result = performance_validation.evaluate(report, Thresholds)

    assert result["passed"] is True
    assert report["streaming_redaction"]["no_leak"] is True
    assert report["large_document_scan"]["findings"] > 0
    assert report["vector_search"]["top_score"] > 0


def test_phase9_provider_failover_summary_requires_safe_fallback():
    safe = performance_validation.provider_failover_summary([
        {"provider": "openai", "ok": False},
        {"provider": "anthropic", "ok": True, "fallback": True},
    ])
    assert safe["safe"] is True

    unsafe = performance_validation.provider_failover_summary([
        {"provider": "openai", "ok": False},
        {"provider": "anthropic", "ok": False, "fallback": True},
    ])
    assert unsafe["safe"] is False
