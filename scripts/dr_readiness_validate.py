import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.production_readiness import disaster_recovery_readiness


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AuthClaw disaster recovery code readiness.")
    parser.add_argument("--fail-on-code-gaps", action="store_true")
    args = parser.parse_args()

    report = disaster_recovery_readiness()
    print(json.dumps(report, indent=2, default=str))
    return 1 if args.fail_on_code_gaps and not report["complete_for_code"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
