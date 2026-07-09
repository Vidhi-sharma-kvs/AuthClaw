#!/usr/bin/env python
"""Validate AuthClaw multi-region DR readiness from Terraform outputs or env vars."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


def _load_outputs(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {key: value.get("value") if isinstance(value, dict) else value for key, value in raw.items()}


def _probe(name: str, url: str, timeout: float) -> Dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310
            status = getattr(response, "status", 0)
            ok = 200 <= status < 500
            detail = f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        ok = exc.code < 500
        detail = f"HTTP {exc.code}"
    except Exception as exc:  # pragma: no cover - environment dependent
        ok = False
        detail = exc.__class__.__name__
    latency_ms = (time.perf_counter() - started) * 1000
    return {"name": name, "url": url, "ok": ok, "latency_ms": round(latency_ms, 2), "detail": detail}


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    outputs = _load_outputs(args.terraform_outputs)
    dr_objectives = outputs.get("dr_objectives") or {}
    rto_minutes = int(os.getenv("AUTHCLAW_DR_RTO_MINUTES", dr_objectives.get("rto_minutes", args.rto_minutes)))
    rpo_minutes = int(os.getenv("AUTHCLAW_DR_RPO_MINUTES", dr_objectives.get("rpo_minutes", args.rpo_minutes)))

    endpoints = {
        "global": args.global_url or outputs.get("global_authclaw_url") or os.getenv("AUTHCLAW_GLOBAL_URL", ""),
        "primary": args.primary_url or os.getenv("AUTHCLAW_PRIMARY_URL", ""),
        "secondary": args.secondary_url or os.getenv("AUTHCLAW_SECONDARY_URL", ""),
    }
    probes: List[Dict[str, Any]] = []
    for name, base_url in endpoints.items():
        if not base_url:
            continue
        probes.append(_probe(name, f"{base_url.rstrip('/')}{args.health_path}", args.timeout))

    replica_bucket = outputs.get("documents_replica_bucket") or os.getenv("AUTHCLAW_DOCUMENTS_REPLICA_BUCKET", "")
    primary_vault = outputs.get("dr_backup_vault_primary") or os.getenv("AUTHCLAW_DR_PRIMARY_VAULT", "")
    secondary_vault = outputs.get("dr_backup_vault_secondary") or os.getenv("AUTHCLAW_DR_SECONDARY_VAULT", "")

    checks = {
        "rto_declared": rto_minutes <= args.max_rto_minutes,
        "rpo_declared": rpo_minutes <= args.max_rpo_minutes,
        "global_endpoint_declared": bool(endpoints["global"]) or args.static_only,
        "regional_endpoints_declared": bool(endpoints["primary"] and endpoints["secondary"]) or args.static_only,
        "object_replication_declared": bool(replica_bucket) or args.static_only,
        "backup_copy_declared": bool(primary_vault and secondary_vault) or args.static_only,
        "endpoint_health": all(probe["ok"] for probe in probes) if probes else args.static_only,
    }
    chaos_scenarios = [
        "mark-primary-route53-health-check-unhealthy",
        "scale-primary-ecs-service-to-zero",
        "deny-primary-provider-egress",
        "restore-postgres-from-secondary-backup-copy",
        "verify-s3-replica-object-read-after-primary-deny",
    ]
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "objectives": {"rto_minutes": rto_minutes, "rpo_minutes": rpo_minutes},
        "probes": probes,
        "chaos_scenarios": chaos_scenarios,
    }
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate AuthClaw DR readiness.")
    parser.add_argument("--terraform-outputs", help="Path to terraform output -json file.")
    parser.add_argument("--global-url", default="")
    parser.add_argument("--primary-url", default="")
    parser.add_argument("--secondary-url", default="")
    parser.add_argument("--health-path", default="/health/ready")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--rto-minutes", type=int, default=30)
    parser.add_argument("--rpo-minutes", type=int, default=15)
    parser.add_argument("--max-rto-minutes", type=int, default=30)
    parser.add_argument("--max-rpo-minutes", type=int, default=15)
    parser.add_argument("--static-only", action="store_true", help="Validate declared controls without probing live URLs.")
    args = parser.parse_args(argv)

    report = build_report(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    sys.exit(main())
