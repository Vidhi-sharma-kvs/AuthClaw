#!/usr/bin/env python
"""Generate a release readiness gate report from repository controls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _exists(path: str) -> bool:
    return (ROOT / path).exists()


def build_report() -> Dict[str, Any]:
    workflow = _read(".github/workflows/ci.yml")
    checks: List[Dict[str, Any]] = [
        {"name": "blocking_bandit", "passed": "bandit -r" in workflow and "bypassing block" not in workflow},
        {"name": "blocking_dependency_scans", "passed": "pip-audit -r requirements.txt --strict" in workflow and "npm audit --audit-level=high" in workflow},
        {"name": "blocking_container_scans", "passed": "aquasecurity/trivy-action" in workflow and 'exit-code: "1"' in workflow},
        {"name": "semgrep_sast", "passed": "semgrep/semgrep-action" in workflow},
        {"name": "red_team_harness", "passed": _exists("scripts/red_team_harness.py") and "scripts/red_team_harness.py" in workflow},
        {"name": "dr_validation", "passed": _exists("scripts/dr_validation.py") and _exists("deployment/aws/dr-runbook.md")},
        {"name": "threat_model", "passed": _exists("docs/threat_model.md")},
        {"name": "release_report", "passed": _exists("docs/release_readiness_report.md")},
        {"name": "srs_traceability", "passed": _exists("docs/srs_traceability_matrix.md")},
    ]
    return {"status": "pass" if all(item["passed"] for item in checks) else "fail", "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AuthClaw release readiness report.")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero when any readiness check fails.")
    args = parser.parse_args()
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 2 if args.strict and report["status"] != "pass" else 0


if __name__ == "__main__":
    raise SystemExit(main())
