#!/usr/bin/env python
"""
AuthClaw load-test wrapper for release checks.

This script uses scripts.gateway_benchmark under sustained concurrency and
emits a JSON report suitable for CI artifacts or manual release notes.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gateway_benchmark import build_headers, run_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AuthClaw gateway load and latency checks.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--bearer", default=None)
    parser.add_argument("--requests", type=int, default=25, help="Requests per endpoint.")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--min-success-rate", type=float, default=0.95)
    parser.add_argument("--max-p95-ms", type=float, default=5000.0)
    parser.add_argument("--output", default="artifacts/load-test-report.json")
    args = parser.parse_args()

    if not args.api_key and not args.bearer:
        parser.error("Provide --api-key or --bearer.")

    report = run_benchmark(
        base_url=args.base_url,
        headers=build_headers(args.api_key, args.bearer),
        requests_per_endpoint=args.requests,
        concurrency=args.concurrency,
        timeout=args.timeout,
        prompt="AuthClaw load-test request. Return one sentence.",
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))

    summary = report["summary"]
    if summary["success_rate"] < args.min_success_rate:
        return 2
    if summary["latency_ms"]["p95"] > args.max_p95_ms:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
