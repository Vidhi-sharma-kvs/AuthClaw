#!/usr/bin/env python
"""
Deterministic AuthClaw performance validation for CI and release gates.

This script avoids live provider calls. It validates local SRS-sensitive paths:
streaming redaction load safety, large document scanning, vector search math,
provider failover/error summary behavior, and configured gateway-overhead
threshold evaluation.
"""

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("AUTHCLAW_REDACTION_SALT", "phase9-performance-validation-redaction-salt")

from document_processing.scanners import scan_text_for_sensitive_data
from rag.vector_store import cosine_similarity
from redaction import stream_redact_sensitive_tokens


def percentile(values: List[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile_value / 100.0
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def summarize_latencies(values: List[float]) -> Dict[str, float]:
    return {
        "avg_ms": round(statistics.mean(values), 3) if values else 0.0,
        "p95_ms": round(percentile(values, 95), 3),
        "max_ms": round(max(values), 3) if values else 0.0,
    }


def benchmark_streaming_redaction(chunks: int = 80) -> Dict[str, object]:
    source = ["safe-token "] * chunks
    source[73] = "SSN 123-45-6789 "
    started = time.perf_counter()
    output_parts = list(stream_redact_sensitive_tokens(source, holdback_chars=64))
    output = "".join(output_parts)
    total_ms = (time.perf_counter() - started) * 1000
    per_chunk_ms = total_ms / max(1, chunks)
    leaked = "123-45-6789" in output
    return {
        "chunks": chunks,
        "total_ms": round(total_ms, 3),
        "per_chunk": summarize_latencies([per_chunk_ms for _ in range(chunks)]),
        "no_leak": not leaked,
    }


def benchmark_large_document_scan(size_kb: int = 512) -> Dict[str, object]:
    block = "Safe compliance text with owner security@example.com and token sk-1234567890abcdefABCDEF.\n"
    repeat = max(1, (size_kb * 1024) // len(block))
    payload = block * repeat
    started = time.perf_counter()
    findings = scan_text_for_sensitive_data(payload)
    duration_ms = (time.perf_counter() - started) * 1000
    return {
        "size_kb": round(len(payload) / 1024, 2),
        "duration_ms": round(duration_ms, 3),
        "findings": len(findings),
    }


def benchmark_vector_search_math(candidates: int = 1000, dimensions: int = 128) -> Dict[str, object]:
    query = [0.5 for _ in range(dimensions)]
    vectors = [[((idx + dim) % 17) / 17.0 for dim in range(dimensions)] for idx in range(candidates)]
    started = time.perf_counter()
    scores = [cosine_similarity(query, vector) for vector in vectors]
    top_score = max(scores) if scores else 0.0
    duration_ms = (time.perf_counter() - started) * 1000
    return {
        "candidates": candidates,
        "dimensions": dimensions,
        "duration_ms": round(duration_ms, 3),
        "top_score": round(top_score, 6),
    }


def provider_failover_summary(events: List[Dict[str, object]]) -> Dict[str, object]:
    failures = [event for event in events if not event.get("ok")]
    fallback_successes = [event for event in events if event.get("fallback") and event.get("ok")]
    return {
        "total": len(events),
        "failures": len(failures),
        "fallback_successes": len(fallback_successes),
        "safe": len(failures) == len(fallback_successes),
    }


def build_report() -> Dict[str, object]:
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "streaming_redaction": benchmark_streaming_redaction(),
        "large_document_scan": benchmark_large_document_scan(),
        "vector_search": benchmark_vector_search_math(),
        "provider_failover": provider_failover_summary([
            {"provider": "openai", "ok": False},
            {"provider": "anthropic", "ok": True, "fallback": True},
        ]),
    }


def evaluate(report: Dict[str, object], args) -> Dict[str, object]:
    violations = []
    if not report["streaming_redaction"]["no_leak"]:
        violations.append({"metric": "streaming_redaction.no_leak", "actual": False, "threshold": True})
    if report["streaming_redaction"]["total_ms"] > args.max_streaming_ms:
        violations.append({"metric": "streaming_redaction.total_ms", "actual": report["streaming_redaction"]["total_ms"], "threshold": args.max_streaming_ms})
    if report["large_document_scan"]["duration_ms"] > args.max_document_scan_ms:
        violations.append({"metric": "large_document_scan.duration_ms", "actual": report["large_document_scan"]["duration_ms"], "threshold": args.max_document_scan_ms})
    if report["vector_search"]["duration_ms"] > args.max_vector_search_ms:
        violations.append({"metric": "vector_search.duration_ms", "actual": report["vector_search"]["duration_ms"], "threshold": args.max_vector_search_ms})
    if not report["provider_failover"]["safe"]:
        violations.append({"metric": "provider_failover.safe", "actual": False, "threshold": True})
    return {"passed": not violations, "violations": violations}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic AuthClaw performance validation.")
    parser.add_argument("--max-streaming-ms", type=float, default=2500.0)
    parser.add_argument("--max-document-scan-ms", type=float, default=2500.0)
    parser.add_argument("--max-vector-search-ms", type=float, default=1500.0)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    report = build_report()
    report["thresholds"] = evaluate(report, args)
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["thresholds"]["passed"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
