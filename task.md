# Tasks Checklist

## Phase 1: Database Migration Setup
- [x] Update `database/migrations.py` to declare SaaS schemas:
  - `tenants`, `tenant_api_keys`, `tenant_credentials`, `policies`, `agent_events`, and `usage_events`.
  - Scoped columns in `chat_sessions` and `chat_messages` (`trace` text field).
- [x] Passwords PBKDF2 & TOTP RFC 6238 utilities (`main.py`)
- [x] Verify migrations run successfully on database startup.


## Phase 2: Onboarding & Auth Core (Backend)
- [x] Implement onboarding endpoints in `main.py`:
  - `POST /auth/register` (email verification token generation).
  - `POST /auth/verify-email` (verifies the token).
  - `GET /auth/domain/verification-token` (generates a DNS TXT value).
  - `POST /auth/domain/verify` (performs real DNS TXT resolver lookups using `dns.resolver`).
- [x] Implement Tenant API Key management endpoints:
  - `POST /keys/generate` (generates raw prefix `ac_` key, stores SHA-256 hash).
  - `GET /keys/list` (retrieves active key metadata).
  - `DELETE /keys/{id}` (revokes key).
- [x] Refactor API authorization middleware:
  - Extract Bearer tokens, hash them using SHA-256, resolve corresponding `tenant_id`, and scope queries.

## Phase 3: Provider secret protection & Routing (Backend)
- [x] Implement encryption/decryption helper using Fernet (symmetric key loaded from environment).
- [x] Implement provider endpoints:
  - `POST /providers/connect` (saves encrypted provider keys).
  - `GET /providers/list` (lists provider connection status).
  - `DELETE /providers/{provider}` (disconnects credentials).
- [x] Refactor LLM routing inside nodes to decrypt and inject tenant-scoped provider credentials.

## Phase 4: Dynamic Orchestration & Tracing (Backend)
- [x] Refactor `nodes/orchestrator_node.py` (Gateway Agent), `nodes/redact_node.py` / `nodes/policy_node.py` (Policy Agent), and `nodes/audit_node.py` (Registrar Agent) to write events to the `agent_events` table at runtime.
- [x] Update `/chat` route to retrieve and append dynamic execution traces from the `agent_events` table.
- [x] 3. Registration, Login & MFA endpoints updates (`main.py`)
- [x] 4. API keys & resolve_tenant modifications (`main.py`)
- [x] 5. Dynamic Compliance Scores endpoint (`main.py`)
- [x] 6. Remove legacy secrets & mock simulators endpoints (`main.py`)
- [x] 7. Create `conftest.py` for isolated unit testing
- [x] 8. Create `run_test_server.py` test server wrapper
- [x] 9. Refactor integration verify scripts
- [x] 10. Frontend updates (`Login.jsx`, `ApprovalQueue.jsx`, `api.js`, `chatService.js`, `AgentStudio.jsx`, `Guardrails.jsx`, `GatewayCenter.jsx`, `TrustCompliance.jsx`, `DevPortal.jsx`)
- [x] 11. Run pytest unit tests & verification scripts, ensure 100% pass rate

## Phase 5: UI Cleanups & Simplification (Frontend)
- [x] Delete `frontend/src/pages/PolicyManager` and remove routes/references.
- [x] Clean up `frontend/src/pages/Dashboard/Dashboard.jsx` to remove charts and mock stats.
- [x] Update `frontend/src/pages/Login/Login.jsx` to support onboarding/registration with verification tabs.
- [x] Update `frontend/src/pages/AgentChat/AgentChat.jsx` to render the dynamic **Multi-Agent Trace** drawer.
- [x] Connect Provider Management UI to call the credentials connect API.
- [x] Connect API Key Management UI.

## Phase 6: Verification & Cleanup
- [x] Fix test assertions in `test_guardrails.py` to handle LLM refusals.
- [x] Run full test suite (`final_verify.py` and `pytest`).
