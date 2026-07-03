# AuthClaw Local Repository Restructuring Report

Date: 2026-07-03

## Scope

This restructuring was local-only. No commit, push, pull request, API change, or feature rewrite was performed.

Runtime modules that are still directly imported by the application were intentionally preserved at the repository root to avoid changing behavior:

- `main.py`
- `graph.py`
- `approval_store.py`
- `memory.py`
- `policy.py`
- `redaction.py`
- `resume.py`
- `retriever.py`
- `risk.py`
- `state.py`
- `verify_audit.py`
- RAG/runtime helper modules

## Before And After Metrics

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| Repository files | 280 | 266 | -14 |
| Text LOC | 36,575 | 36,524 | -51 |
| Code/config LOC | 34,479 | 34,524 | +45 |
| Root-level test files | 43 | 0 | -43 |
| Root-level verification/diagnostic scripts | 8 | 0 | -8 |
| Tracked generated evidence reports | 12 | 0 | -12 |

Metrics include hidden source/config files such as `.github/`, `.gitignore`, and `.dockerignore`, while honoring `.gitignore` for local secrets and generated artifacts. Code/config LOC increased slightly because `tools/verification/run_test_server.py` was normalized after moving and this report was added.

## Folder Structure Before

The repository root previously mixed runtime code with tests, diagnostics, generated reports, and historical notes:

```text
AuthClaw/
  main.py
  graph.py
  services/
  routers/
  database/
  frontend/
  gateway-go/
  deployment/
  test_*.py
  conftest.py
  verify*.py
  final_verify.py
  run_test_server.py
  provider_test.py
  check_trace.py
  evidence/*.txt
  task.md
  walkthrough.md
  frontend/query
```

## Folder Structure After

The root is now reserved for runtime entry points, package directories, deployment files, and project metadata:

```text
AuthClaw/
  .github/
  data/
  database/
  deployment/
  docs/
  document_processing/
  frontend/
  gateway-go/
  graphs/
  nodes/
  providers/
  rag/
  routers/
  scripts/
  services/
  startup/
  tests/
  tools/
  main.py
  graph.py
  approval_store.py
  memory.py
  policy.py
  redaction.py
  requirements.txt
  Dockerfile
  docker-compose.production.yml
```

New organization:

| Path | Contents |
| --- | --- |
| `tests/` | All pytest suites and `conftest.py` |
| `tests/fixtures/` | Test fixture files such as `test_security_policy.txt` |
| `tools/verification/` | Local verification harnesses and smoke-test scripts |
| `tools/diagnostics/` | Developer diagnostics not used by runtime |

## Files Moved

- Root `test_*.py` files moved to `tests/`.
- Root `conftest.py` moved to `tests/conftest.py`.
- Root `test_security_policy.txt` moved to `tests/fixtures/test_security_policy.txt`.
- Root `verify*.py`, `verify.ps1`, `final_verify.py`, and `run_test_server.py` moved to `tools/verification/`.
- Root `provider_test.py` and `check_trace.py` moved to `tools/diagnostics/`.

## Files Removed

Removed only generated/obsolete clutter:

- `evidence/Compliance_Report_doc_*.txt`
- `evidence/Findings_Report_doc_*.txt`
- `evidence/Risk_Report_doc_*.txt`
- `frontend/query`
- `task.md`
- `walkthrough.md`
- Local generated caches/build outputs after verification:
  - `frontend/dist/`
  - `.pytest_cache/`
  - `.gocache/`
  - `.npm-cache/`
  - `.docker-local/`
  - `logs/`
  - Python `__pycache__/` directories
- Ignored local scratch outputs:
  - `scratch/`
  - `watched_documents/`

No runtime feature files, routes, services, database tables, frontend pages, or APIs were removed.

Local secret/runtime files such as `.env`, `.env.txt`, `authclaw-key.pem`, and `authclaw.pem` were preserved because deleting them could break local access or deployment workflows. They are ignored by Git and excluded from source metrics.

## Reference Updates

- `pytest.ini` now sets `pythonpath = .` and `testpaths = tests`.
- `.github/workflows/ci.yml` Bandit exclusions now match the moved verification and diagnostic tools.
- `.gitignore` ignores local assistant metadata, generated evidence, and local cache folders.
- `.dockerignore` excludes non-runtime folders such as tests, docs, tools, caches, and local secrets from image build contexts.
- `tools/verification/run_test_server.py` now resolves paths from the repository root.
- `tools/verification/verify.ps1` now uses `tests/fixtures/test_security_policy.txt`.
- Phase/reference docs now point at `tests/...` where needed.
- `scripts/start-local.ps1` now sets workspace-local `GOCACHE` when no Go cache is configured, avoiding Windows build-cache permission failures.

## Duplicate / Dead Code Handling

| Item | Action |
| --- | --- |
| Duplicate `os` import in `verify_rag_endpoints.py` | Removed |
| Runtime duplicate utilities | No merge performed; no safe duplicate runtime utility was proven equivalent |
| Dead runtime code | None removed |
| Generated evidence reports | Removed |
| Accidental `frontend/query` file | Removed |

## Verification Results

| Check | Result | Evidence |
| --- | --- | --- |
| Backend tests | PASS | `118 passed, 1 skipped, 2 warnings in 326.21s` |
| Frontend lint | PASS | `npm run lint` completed with 0 errors and 56 existing warnings |
| Frontend build | PASS | `npm run build` completed successfully |
| Python security scan | PASS | Bandit reported `No issues identified` |
| Frontend dependency audit | PASS | `npm audit --audit-level=high` reported `found 0 vulnerabilities` |
| Go tests | PASS | `go test ./...` passed with workspace `GOCACHE` |
| Backend Docker build | PASS | `docker build -t authclaw-api:local-structure -f Dockerfile .` completed |
| Frontend Docker build | BLOCKED BY ENVIRONMENT | Docker Hub pulls for `node:22-alpine` and `nginx:1.27-alpine` failed with TLS/DNS timeouts; images were not present locally |
| Terraform fmt | PASS | `terraform fmt -check -recursive` completed |
| Terraform init | PASS | `terraform init -backend=false` completed after network approval |
| Terraform validate | PASS | `Success! The configuration is valid.` |
| Local startup | PASS | Backend `8000`, Go Gateway `9000`, Frontend `5173`, and gateway auth preflight all returned healthy responses |
| Local shutdown | PASS | `scripts/stop-local.ps1` stopped processes on ports `8000`, `9000`, and `5173` |

## Remaining Verification Blocker

The only incomplete verification item is frontend Docker build. The repository build command is correct, but Docker could not pull required base images:

```text
node:22-alpine
nginx:1.27-alpine
```

Observed Docker error:

```text
TLS handshake timeout
```

Once Docker Hub connectivity is stable or those base images are available locally, rerun:

```powershell
$env:DOCKER_CONFIG = "$PWD\.docker-local"
docker pull node:22-alpine
docker pull nginx:1.27-alpine
docker build -t authclaw-frontend:local-structure -f frontend/Dockerfile frontend
```

## Commit / Push Status

No commit was created.

No push was performed.

These changes are waiting for review and approval.
