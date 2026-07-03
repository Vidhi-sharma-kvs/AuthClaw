# Backend API

The AuthClaw Python backend currently uses the repository root as its stable
runtime package boundary for backward compatibility.

Primary source:

- `../../main.py`
- `../../routers/`
- `../../services/`
- `../../database/`
- `../../document_processing/`
- `../../providers/`
- `../../nodes/`
- `../../graphs/`

This folder intentionally contains only an index. Moving the runtime files here
would require a package migration and is kept out of the GitHub presentation
cleanup to avoid changing behavior.
