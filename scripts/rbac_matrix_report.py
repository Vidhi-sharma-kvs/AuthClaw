import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app
from services.rbac_matrix import matrix_markdown, report_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate AuthClaw RBAC permission matrix.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    content = matrix_markdown(app) if args.format == "markdown" else report_json(app)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
