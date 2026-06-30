# Phase 3 - Document Governance Gateway

## What changed

Phase 3 adds a gateway-native document redaction flow without replacing the existing document upload, RAG, or chat features.

New endpoint:

```http
POST /gateway/documents/redact
```

The endpoint accepts a file upload, resolves the tenant from the session token or AuthClaw API key, extracts document text, applies existing AuthClaw redaction policies, writes audit evidence, records gateway lifecycle metadata, and returns the redacted text with a multi-agent trace.

## Runtime flow

```text
Customer / AuthClaw UI
-> /gateway/documents/redact
-> Gateway Agent
-> Security Agent
-> Policy Agent
-> Audit Agent
-> Registrar Agent
-> Redacted document response
```

## Supported file types

Supported now:

- PDF
- DOCX
- TXT
- Markdown
- CSV
- XLS/XLSX

Image uploads are rejected with a clear OCR-not-enabled message. OCR can be enabled later with an explicit image extraction dependency and deployment package.

## Frontend behavior

Gateway Chat now includes a document upload control. Uploaded documents are processed through the gateway redaction endpoint and displayed as an inspected output card with:

- request ID
- tenant ID
- decision
- risk level
- redacted field count
- redacted document text
- execution trace

## Why this belongs in AuthClaw

AuthClaw is the governance layer between enterprise users and LLM/provider workflows. Documents often contain emails, Aadhaar numbers, secrets, customer data, and internal policy text. The Phase 3 flow lets customers inspect and redact sensitive document content before that content is sent to a model or copied into a downstream app.

## Backward compatibility

No existing routes were removed. Existing endpoints remain available:

- `/gateway/chat`
- `/chat`
- `/v1/chat/completions`
- `/documents/upload`
- `/documents/scan`
- `/documents/chat`
