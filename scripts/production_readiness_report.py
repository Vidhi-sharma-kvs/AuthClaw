import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
from services.production_readiness import production_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AuthClaw code-only production readiness report.")
    parser.add_argument("--output", default="")
    parser.add_argument("--fail-on-code-gaps", action="store_true")
    args = parser.parse_args()

    report = production_readiness_report(app)
    content = json.dumps(report, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)
    return 1 if args.fail_on_code_gaps and not report["complete_for_code"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
