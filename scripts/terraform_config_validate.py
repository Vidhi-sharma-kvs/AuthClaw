import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.production_readiness import terraform_coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Terraform coverage for AuthClaw production dependencies.")
    parser.add_argument("--root", default="deployment/terraform")
    parser.add_argument("--fail-on-missing", action="store_true")
    args = parser.parse_args()

    report = terraform_coverage(args.root)
    print(json.dumps(report, indent=2, default=str))
    return 1 if args.fail_on_missing and not report["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
