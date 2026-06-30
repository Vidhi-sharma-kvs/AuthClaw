#!/usr/bin/env python
"""
AuthClaw gateway latency and compatibility benchmark.

Examples:
    python scripts/gateway_benchmark.py --base-url http://127.0.0.1:8000 --api-key ac_xxx
    python scripts/gateway_benchmark.py --base-url http://13.62.54.79 --bearer eyJ...
"""

import argparse
import json
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional

import requests


DEFAULT_PROMPT = "AuthClaw benchmark request. Explain AI gateway governance in one sentence."


@dataclass
class BenchmarkResult:
    endpoint: str
    status_code: int
    latency_ms: float
    ok: bool
    request_id: Optional[str] = None
    error: Optional[str] = None


def percentile(values: List[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * (percentile_value / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def summarize(results: Iterable[BenchmarkResult]) -> Dict[str, object]:
    result_list = list(results)
    latencies = [item.latency_ms for item in result_list if item.ok]
    status_codes: Dict[str, int] = {}
    for item in result_list:
        key = str(item.status_code)
        status_codes[key] = status_codes.get(key, 0) + 1

    total = len(result_list)
    successes = sum(1 for item in result_list if item.ok)
    failures = total - successes

    return {
        "total_requests": total,
        "successes": successes,
        "failures": failures,
        "success_rate": round(successes / total, 4) if total else 0.0,
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0.0,
            "max": round(max(latencies), 2) if latencies else 0.0,
            "avg": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "p50": round(percentile(latencies, 50), 2),
            "p95": round(percentile(latencies, 95), 2),
            "p99": round(percentile(latencies, 99), 2),
        },
        "status_codes": status_codes,
    }


def build_headers(api_key: Optional[str], bearer: Optional[str]) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = bearer if bearer.startswith("Bearer ") else f"Bearer {bearer}"
    elif api_key:
        headers["X-API-Key"] = api_key
    return headers


def benchmark_gateway_chat(base_url: str, headers: Dict[str, str], timeout: float, prompt: str) -> BenchmarkResult:
    endpoint = "/gateway/chat"
    payload = {
        "session_id": f"bench-{uuid.uuid4()}",
        "message": prompt,
    }
    return post_json(base_url, endpoint, headers, payload, timeout)


def benchmark_openai_chat(base_url: str, headers: Dict[str, str], timeout: float, prompt: str) -> BenchmarkResult:
    endpoint = "/v1/chat/completions"
    payload = {
        "model": "authclaw-gateway",
        "messages": [{"role": "user", "content": prompt}],
    }
    return post_json(base_url, endpoint, headers, payload, timeout)


def post_json(base_url: str, endpoint: str, headers: Dict[str, str], payload: Dict[str, object], timeout: float) -> BenchmarkResult:
    url = f"{base_url.rstrip('/')}{endpoint}"
    started = time.perf_counter()
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency_ms = (time.perf_counter() - started) * 1000
        request_id = None
        try:
            body = response.json()
            request_id = body.get("request_id")
        except ValueError:
            body = {}
        ok = response.status_code < 500 and response.status_code not in {401, 403, 404, 405}
        error = None if ok else body.get("detail") or body.get("error") or response.text[:300]
        return BenchmarkResult(endpoint, response.status_code, latency_ms, ok, request_id, error)
    except requests.RequestException as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return BenchmarkResult(endpoint, 0, latency_ms, False, error=str(exc))


def run_benchmark(
    *,
    base_url: str,
    headers: Dict[str, str],
    requests_per_endpoint: int,
    concurrency: int,
    timeout: float,
    prompt: str,
) -> Dict[str, object]:
    tasks = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(requests_per_endpoint):
            tasks.append(pool.submit(benchmark_gateway_chat, base_url, headers, timeout, prompt))
            tasks.append(pool.submit(benchmark_openai_chat, base_url, headers, timeout, prompt))

        results = [future.result() for future in as_completed(tasks)]

    by_endpoint = {}
    for endpoint in sorted({item.endpoint for item in results}):
        by_endpoint[endpoint] = summarize([item for item in results if item.endpoint == endpoint])

    return {
        "base_url": base_url.rstrip("/"),
        "requests_per_endpoint": requests_per_endpoint,
        "concurrency": concurrency,
        "summary": summarize(results),
        "endpoints": by_endpoint,
        "failures": [asdict(item) for item in results if not item.ok],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark AuthClaw gateway latency and route compatibility.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--bearer", default=None)
    parser.add_argument("--requests", type=int, default=5, help="Requests per endpoint.")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--max-p95-ms", type=float, default=None)
    parser.add_argument("--min-success-rate", type=float, default=1.0)
    parser.add_argument("--output", default=None, help="Optional JSON report path.")
    args = parser.parse_args()

    if args.requests < 1:
        parser.error("--requests must be at least 1")
    if args.concurrency < 1:
        parser.error("--concurrency must be at least 1")
    if not args.api_key and not args.bearer:
        parser.error("Provide --api-key or --bearer")

    report = run_benchmark(
        base_url=args.base_url,
        headers=build_headers(args.api_key, args.bearer),
        requests_per_endpoint=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
        prompt=args.prompt,
    )

    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")

    summary = report["summary"]
    if summary["success_rate"] < args.min_success_rate:
        return 2
    if args.max_p95_ms is not None and summary["latency_ms"]["p95"] > args.max_p95_ms:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
