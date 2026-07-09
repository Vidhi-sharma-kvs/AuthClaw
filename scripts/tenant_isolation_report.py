import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.tenant_isolation_report import tenant_isolation_markdown, tenant_isolation_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AuthClaw tenant isolation coverage report.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", default="")
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    report = tenant_isolation_report()
    content = tenant_isolation_markdown() if args.format == "markdown" else json.dumps(report, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)
    return 1 if args.fail_on_gaps and not report["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
