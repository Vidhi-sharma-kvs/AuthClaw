# AuthClaw Walkthrough: Architecture & Engineering Reference

AuthClaw is a production-grade enterprise AI Gateway and Compliance Guardrail platform designed to secure, monitor, and audit Large Language Model (LLM) workflows. It provides real-time security scanning, automated PII masking, cryptographic audit chains, and human-in-the-loop (HITL) approval states.

---

## 1. Executive Summary & Business Problem

### What is AuthClaw?
AuthClaw is an intermediary intelligence layer (reverse proxy and guardrail gateway) that sits between enterprise clients (or AI agents) and LLM providers. By intercepting inbound prompts and outbound responses, AuthClaw enforces security policies, prevents data exfiltration, detects prompt injections, and manages approval workflows before requests ever reach public LLM APIs.

### The Business Problem
1. **Data Leakage & Compliance Violation**: Employees and automated agents inadvertently upload sensitive data—such as Social Security Numbers (SSNs), Aadhaar numbers, health data (PHI), credit cards, or proprietary source code—to public LLMs, violating regulations like **GDPR**, **HIPAA**, and **SOC2**.
2. **Lack of Auditability**: Standard API gateway logs are mutable and easily tampered with, offering no proof of compliance to auditors.
3. **Adversarial Exploitations**: Prompt injections and jailbreak attempts can manipulate enterprise AI agents into executing unauthorized actions (e.g., database purging, privilege escalation).
4. **Provider Lock-in & Downtime**: Outages in single providers (like OpenAI or Anthropic) halt operations if developers fail to build robust, multi-region fallback mechanisms.

---

## 2. High-Level Architecture

AuthClaw is structured as a decoupled web application composed of:
1. **Frontend Console**: React, Vite, and Tailwind CSS SPA serving as the management dashboard.
2. **Backend API Gateway**: A FastAPI-based high-performance server managing incoming LLM requests, route registry, metrics aggregates, and security check nodes.
3. **Agent State Graph**: A structured workflow router powered by LangGraph that orchestrates prompt redaction, policy evaluation, risk classification, approval loops, RAG context enrichment, and LLM providers execution.
4. **Relational Database**: PostgreSQL storing audit trails, client tenants, active gateway routes, security policies, API keys, compliance evidence, and ephemeral worker records.

### System Architecture Diagram (ASCII)

```text
  +---------------------------------------------------------------------------------+
  |                                  FRONTEND CONSOLE                               |
  |                        (React + Vite + Tailwind + Chart.js)                    |
  +---------------------------------------+-----------------------------------------+
                                          |
                                 REST APIs (HTTP)
                                          |
                                          v
  +---------------------------------------------------------------------------------+
  |                                 FASTAPI BACKEND                                 |
  |                                                                                 |
  |  +--------------------+  +----------------------+  +-------------------------+  |
  |  |    REST Services   |  |   Gateway API (OAI)  |  |   Metrics Synchronizer  |  |
  |  +---------+----------+  +----------+-----------+  +------------+------------+  |
  |            |                        |                           |               |
  |            |                        v                           v               |
  |            |             +----------------------+      +-----------------+      |
  |            |             |   LangGraph Agent    |      |  PostgreSQL DB  |      |
  |            |             |   Orchestrator Flow  |      |  (SQLAlchemy)   |      |
  |            |             +----------+-----------+      +--------+--------+      |
  |            |                        |                           ^               |
  |            +------------------------+---------------------------+               |
  +-------------------------------------|-------------------------------------------+
                                        |
                                        v
                            +-----------------------+
                            |     LLM PROVIDERS     |
                            |  (Gemini, OpenAI,     |
                            |   Anthropic, Cohere)  |
                            +-----------------------+
```

### End-to-End Sequence Diagram

```text
Client / Agent             FastAPI Gateway           LangGraph / Nodes           LLM Provider           PostgreSQL DB
      |                          |                           |                         |                      |
      |--- Inbound Query ------->|                           |                         |                      |
      |    (e.g., Prompt)        |--- Start Workflow ------->|                         |                      |
      |                          |                           |--- Apply Redaction ---->|                      |
      |                          |                           |    (Mask PII)           |                      |
      |                          |                           |                         |                      |
      |                          |                           |--- Check Policies ----->|                      |
      |                          |                           |    (Block keywords)     |                      |
      |                          |                           |                         |                      |
      |                          |                           |--- Compute Risk ------->|                      |
      |                          |                           |    (LOW / MED / HIGH)   |                      |
      |                          |                           |                         |                      |
      |                          |    [If Risk is HIGH]      |                         |                      |
      |                          |    Trigger HITL Approval  |                         |                      |
      |                          |    State Machine          |                         |                      |
      |                          |<-- PENDING_APPROVAL ------|                         |                      |
      |                          |                           |                         |                      |
      |<-- Return approval_id ---|                           |                         |                      |
      |                          |                           |                         |                      |
      |--- MFA Confirm --------->|                           |                         |                      |
      |    (Approve Event)       |--- Mark Approved -------->|                         |                      |
      |                          |                           |                         |                      |
      |                          |                           |--- Enrich Context ----->|                      |
      |                          |                           |    (RAG Chunks)         |                      |
      |                          |                           |                         |                      |
      |                          |                           |--- Call Provider ------>|                      |
      |                          |                           |    (e.g. Gemini API)    |                      |
      |                          |                           |                         |                      |
      |                          |                           |<-- Response Raw --------|                      |
      |                          |                           |                                                |
      |                          |                           |--- Append to Cryptographic Audit Chain ------->|
      |                          |                           |    (SHA-256 Linkage)                           |
      |                          |                           |                                                |
      |                          |                           |--- Write Gateway Metrics Aggregates ---------->|
      |                          |<-- Processed Response ----|                                                |
      |<-- API Response ---------|                                                                            |
```

---

## 3. Project Directory Structure

```text
AuthClaw/
├── .env                              # API Key, URLs, and Provider configurations
├── main.py                           # Core FastAPI application endpoints and lifecycle
├── graph.py                          # LangGraph state router definitions
├── state.py                          # Shared execution state model for LangGraph workflow
├── policy.py                         # Policy loading, caching, and validation utility
├── redaction.py                      # PII masking regex logic and hash calculations
├── risk.py                           # Risk level classifier using keyword evaluation
├── verify_audit.py                   # Cryptographic audit hash chaining and verification
├── approval_store.py                 # HITL pending approval runtime registry
├── retriever.py                      # Context retriever querying documents database
├── chunker.py                        # Document parser chunk utility
├── rag_loader.py                     # Document indexing wrapper
├── database/
│   ├── __init__.py                   # DB Engine and Session startup
│   └── migrations.py                 # DB Migrations schema & automatic seeding logic
├── nodes/
│   ├── orchestrator_node.py          # Determines compliance task type (GDPR, HIPAA, etc.)
│   ├── redact_node.py                # Intercepts prompt to mask sensitive details
│   ├── policy_node.py                # Assesses prompt against policy blocked keywords
│   ├── risk_node.py                  # Classifies risk level
│   ├── approval_node.py              # Suspends workflow for HITL if risk is HIGH
│   ├── rag_node.py                   # Retrieves local knowledge chunks
│   ├── llm_node.py                   # Calls LLM providers (Google Gemini)
│   └── audit_node.py                 # Finalizes record logging (File + Database)
├── providers/
│   ├── __init__.py                   # Provider routing switch
│   ├── base.py                       # Abstract base class for providers
│   ├── config.py                     # Environment maps (Keys, Models)
│   └── gemini_provider.py            # Google Gemini API REST client implementation
├── docs/
│   └── AUTHCLAW_WALKTHROUGH.md       # Comprehensive system walkthrough document (THIS FILE)
└── frontend/                         # React Client Portal
    ├── src/
    │   ├── components/               # Layout, Navigation Sidebar, Common templates
    │   ├── pages/                    # Portal tabs (Dashboard, Security, Trust, etc.)
    │   ├── router/                   # App Routing configuration
    │   └── services/                 # Axios clients and Backend connection channels
    ├── package.json                  # Frontend dependencies
    └── vite.config.js                # Vite build options
```

---

## 4. Backend Orchestration Details

### 4.1. OpenAI-Compatible & Gemini Provider Integration
AuthClaw exposes an OpenAI-compatible endpoint at `/v1/chat/completions`, allowing it to act as a drop-in replacement for OpenAI SDKs. It redirects requests internally to Google Gemini or other providers based on configuration.

The [GeminiProvider](file:///c:/Users/VIDHI SHARMA/Documents/New folder (2)/OneDrive/Desktop/AuthClaw/providers/gemini_provider.py) maps parameters (e.g. `messages` history) to the Gemini REST API format:
- Inbound roles `user` and `assistant` are mapped to Gemini's `user` and `model`.
- System instructions are parsed and sent in the payload's `systemInstruction` field.
- The request is executed against: `https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GOOGLE_API_KEY}`.
- If the environment API key is configured as `"dummy"`, it triggers a mock response fallback, allowing seamless test executions without external dependencies.

### 4.2. LangGraph Security Node Workflows
The request is processed sequentially via an execution graph:
1. **orchestrator_node**: Evaluates context and categorizes the task (e.g. general, GDPR, HIPAA, SOC2).
2. **redact_node**: Intercepts request message and applies PII redaction.
3. **policy_node**: Inspects for blocked keywords.
4. **Conditional Route (policy_node -> risk_node or audit_node)**:
   - If blocked, execution routes directly to the audit logging node.
   - If allowed, execution routes to the risk classification node.
5. **risk_node**: Assesses risk levels (LOW, MEDIUM, HIGH) dynamically.
6. **approval_node**: Suspends the thread, generating a `PENDING_APPROVAL` status if risk is HIGH.
7. **Conditional Route (approval_node -> rag_node or audit_node)**:
   - If approval is granted, routes to the RAG retrieval node.
   - If rejected or expired, routes directly to the audit logging node.
8. **rag_node**: Queries the database to retrieve relevant context.
9. **llm_node**: Combines context and historical dialogue history to call the Google Gemini API.
10. **audit_node**: Commits the audit transaction to the file system and SQL cryptographic tables.

### 4.3. Advanced Guardrails & Redaction Engine
The redaction engine ([redaction.py](file:///c:/Users/VIDHI SHARMA/Documents/New folder (2)/OneDrive/Desktop/AuthClaw/redaction.py)) inspects text for specific patterns using regular expressions:
- **Credit Cards**: `\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b`
- **Aadhaar Numbers**: `\b\d{4}\s\d{4}\s\d{4}\b`
- **Emails**: `[\w\.-]+@[\w\.-]+\.\w+`
- **Phone Numbers**: `\b\d{10}\b`

Depending on the configuration in the active policy, it applies one of these strategies:
- **Mask**: Returns partially masked values (e.g., `v*****a@domain.com` or `******4321` for credit cards).
- **Hash**: Replaces the match with a deterministic SHA-256 slice: `[HASH_a1b2c3d4...]`.
- **Synthetic**: Replaces sensitive data with mock synthetic placeholders (e.g. `synthetic.email@example.com`).
- **Redact**: Replaces with standard markers (e.g. `[REDACTED_CARD]`).

### 4.4. Human-In-The-Loop (HITL) Workflow State Machine
When a query contains high-risk keywords (e.g., "delete", "production database", "drop table"), the system suspends execution:
1. **READ_ONLY / PLAN**: Initial assessment states.
2. **PENDING_APPROVAL**: A unique `approval_id` is returned, and execution is paused.
3. **MFA Confirmation**: Approvals require entering a multi-factor authorization token (`123456`).
4. **APPROVED**: Changes the state to approved.
5. **EXECUTING / COMPLETED**: The client triggers the endpoint `/execute/{approval_id}` which executes the original prompt against the LLM.
6. **REJECTED**: If rejected, the workflow halts.
7. **EXPIRED**: An expiration timer runs. Once elapsed, the state automatically becomes `expired`.

### 4.5. Cryptographic Hash-Chain Verification (Tamper-Evidence)
To guarantee database integrity, AuthClaw implements SHA-256 cryptographic hash-chaining on all audit logs.
- The genesis block (first record) uses a `previous_hash` of `"0" * 64`.
- Every subsequent record recalculates its `integrity_hash` using:
  $$\text{hash} = \text{SHA256}(\text{record\_id} \mathbin{\Vert} \text{user\_query} \mathbin{\Vert} \text{response} \mathbin{\Vert} \text{allowed} \mathbin{\Vert} \text{created\_at} \mathbin{\Vert} \text{risk\_level} \mathbin{\Vert} \text{approval\_status} \mathbin{\Vert} \text{previous\_hash})$$
- The database stores both `previous_hash` and `integrity_hash` fields.
- The `/audit/verify` endpoint runs a full check to verify the chain. It flags:
  1. **ID Gaps**: Missing record IDs (indicating record deletions).
  2. **Link Gaps**: Mismatched previous hashes (indicating record insertions or swaps).
  3. **Hash Gaps**: Recalculated hash mismatches (indicating text alterations or tampering).

---

## 5. Database Schema Overview

All tables are defined in [database/migrations.py](file:///c:/Users/VIDHI SHARMA/Documents/New folder (2)/OneDrive/Desktop/AuthClaw/database/migrations.py):

### 1. `audit_logs`
Stores the tamper-evident records of security events.
- `id` (SERIAL PRIMARY KEY)
- `user_query` (TEXT)
- `response` (TEXT)
- `allowed` (BOOLEAN)
- `created_at` (TIMESTAMP)
- `risk_level` (VARCHAR)
- `approval_status` (VARCHAR)
- `integrity_hash` (VARCHAR(64))
- `previous_hash` (VARCHAR(64))

### 2. `gateway_requests`
Stores request history and latencies for the metrics engine.
- `id` (SERIAL PRIMARY KEY)
- `timestamp` (TIMESTAMP)
- `risk_level` (VARCHAR)
- `allowed` (BOOLEAN)
- `status` (VARCHAR)
- `request_id` (VARCHAR)
- `tenant_id` (VARCHAR)
- `route_id` (VARCHAR)
- `provider` (VARCHAR)
- `model` (VARCHAR)
- `latency` (INTEGER)
- `tokens_in` (INTEGER)
- `tokens_out` (INTEGER)

### 3. `gateway_routes`
Configures active route destinations.
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR)
- `provider` (VARCHAR)
- `endpoint` (VARCHAR)
- `model` (VARCHAR)
- `rate_limit` (INTEGER)
- `redaction_enabled` (BOOLEAN)
- `enabled` (BOOLEAN)
- `tenant_assignment` (VARCHAR)

### 4. `tenants`
Tracks isolated tenant allocations.
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR UNIQUE)
- `status` (VARCHAR)
- `usage_count` (INTEGER)
- `tokens_used` (INTEGER)

### 5. `secrets`
Manages API keys and rotation intervals.
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR)
- `provider` (VARCHAR)
- `key_hash` (VARCHAR)
- `expiry` (VARCHAR)
- `last_rotated` (VARCHAR)
- `rotation_count` (INTEGER)

### 6. `policies`
Defines active compliance configurations.
- `id` (SERIAL PRIMARY KEY)
- `name` (VARCHAR)
- `type` (VARCHAR)
- `rules` (TEXT - JSON ruleset)
- `enabled` (BOOLEAN)

### 7. `knowledge_documents` & `knowledge_chunks`
Vector store storage for RAG documents and raw index text fragments.
- `id` (SERIAL PRIMARY KEY)
- `document_id` (INTEGER)
- `content` (TEXT)
- `embedding_preview` (VARCHAR)

---

## 6. Core API Registry & Payload Formats

### 6.1. Inbound Chat Gateway
- **Endpoint**: `/chat`
- **Method**: `POST`
- **Headers**: `x-api-key: authclaw-secret-key`
- **Request Body**:
  ```json
  {
    "session_id": "session-xyz-123",
    "message": "Verify compliance details for my credit card 4111-2222-3333-4444"
  }
  ```
- **Response (Allowed & Redacted)**:
  ```json
  {
    "response": "The details have been indexed. Note: card 4111-****-****-4444 has been securely processed.",
    "risk_level": "LOW"
  }
  ```

- **Response (Blocked/Pending Approval due to High Risk)**:
  ```json
  {
    "risk_level": "HIGH",
    "approval_status": "PENDING_APPROVAL",
    "approval_id": "app-8c7e2b-f3a1..."
  }
  ```

### 6.2. Human-In-The-Loop Approval Action
- **Endpoint**: `/approve/{approval_id}`
- **Method**: `POST`
- **Request Body**:
  ```json
  {
    "mfa_code": "123456"
  }
  ```
- **Response**:
  ```json
  {
    "message": "Request Approved",
    "approval_id": "app-8c7e2b-f3a1...",
    "status": "approved"
  }
  ```

### 6.3. Retrieve Cryptographic Integrity State
- **Endpoint**: `/audit/verify`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "valid": true,
    "records_checked": 42,
    "chain_started_at": "2026-06-17T12:00:00Z"
  }
  ```

---

## 7. Frontend Portal Overview

The frontend interface comprises 11 functional sections:
1. **Overview Dashboard**: Displays live counts for gateway latency, compliance indices, blocked payloads, and charts detailing daily requests, risk levels, and provider utilization.
2. **Agent Chat**: A playground interface showcasing active PII redaction and policy-blocked responses in real-time.
3. **Gateway Center**: Controls routes, edits providers, reviews latencies, and rotates credentials.
4. **Guardrails & Redaction**: Interactive interface with policy editors, live PII redaction sandboxes, and token stream inspectors.
5. **Agent Studio & RAG**: Visualizes orchestrator nodes, uploads files, indexes RAG segments, and runs ephemeral workers.
6. **Approval Center**: Displays HITL workflows with status indicators (PENDING, APPROVED, EXECUTED, REJECTED, EXPIRED).
7. **Trust & Compliance**: Computes compliance readiness scores dynamically based on active rules.
8. **Security & Red Team**: Simulates prompt injections and jailbreaks, detailing the findings.
9. **Audit Explorer**: Verifies SHA-256 chain integrity, displaying log details, hashes, and verification statuses.
10. **Access Control (RBAC)**: Manages users and permission levels.
11. **Developer Portal**: Provides OpenAPI documentation, API sandbox clients, and SDK code snippets.

---

## 8. End-to-End Request Journey

Here is the step-by-step path a query takes:
1. **Client Submission**: A client app submits a chat payload.
2. **API Key Authentication**: AuthClaw checks the request header.
3. **Task Orchestration**: The prompt is processed through the LangGraph agent state graph.
4. **PII Masking**: Regular expressions mask any sensitive identifiers.
5. **Policy Verification**: Blocked keywords are flagged. If matched, the request is marked as blocked and routes straight to the audit node.
6. **Risk Analysis**: Checks for high-risk keywords. If found, a pending approval record is created, and the prompt is paused.
7. **RAG Context Enrichment**: If allowed or approved, relevant context chunks are fetched from the database.
8. **LLM Provider Execution**: The prompt is compiled and sent to the LLM (e.g., Google Gemini).
9. **Cryptographic Auditing**: Details are appended to the hash chain in `audit_logs`.
10. **Metrics Updates**: Counts are updated in `gateway_requests` to refresh the dashboard graphs.

---

## 9. Future Roadmap

1. **Self-Healing Failovers**: Automatically test and cycle route priorities if a region drops.
2. **Vector DB Integration**: Use external vector databases (such as Chroma or Pinecone) for handling large RAG loads.
3. **Custom Redaction Training**: Train lightweight tokenizers to identify proprietary IP and code blocks.
4. **Decentralized Consensus Auditing**: Replicate the hash chain across multiple nodes to make tampering impossible.
5. **FIDO2/WebAuthn MFA**: Upgrade approval validation to support biometrics and physical security keys.
