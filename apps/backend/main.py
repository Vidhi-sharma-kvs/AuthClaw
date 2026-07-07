"""
Monorepo-compatible FastAPI entrypoint.

The stable backend source still lives at the repository root. This wrapper lets
tools target apps/backend without breaking current imports, Dockerfiles, or
local developer commands.
"""
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from main import app  # noqa: E402,F401
