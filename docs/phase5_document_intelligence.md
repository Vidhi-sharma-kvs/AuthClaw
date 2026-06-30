# Phase 5 - Document, PDF, and Image Analysis

Phase 5 turns AuthClaw Chat into a secure document intelligence gateway.

## User Flow

```text
Upload PDF / DOCX / Image / Text
-> Extract text
-> OCR when image or scanned PDF support is available
-> Security Agent detects sensitive data and secrets
-> Policy Agent applies tenant policy actions
-> Audit Agent stores evidence
-> User downloads redacted PDF or JSON findings report
-> User can ask questions against the sanitized document text
```

## Supported Inputs

- PDF
- DOCX
- TXT / Markdown
- CSV
- XLSX / XLS
- PNG
- JPG / JPEG
- TIFF / TIF

Images and scanned PDFs require OCR dependencies and system binaries:

- `pytesseract`
- `Pillow`
- `pdf2image`
- Tesseract OCR binary
- Poppler utilities for scanned PDF page rendering

If OCR is not installed, AuthClaw returns a clear `422` error explaining the missing OCR capability.

## Outputs

The document gateway response includes:

- `redacted_text`
- `redacted_pdf_base64`
- `findings_report`
- page-aware `findings`
- request trace
- audit record
- gateway request lifecycle record

Each finding includes field type, page/location, confidence, and action taken.

## Security Behavior

PII is redacted, masked, hashed, or tokenized according to policy. Secrets such as API keys, JWTs, and AWS keys produce a `BLOCK` decision while still returning a sanitized artifact for safe review.
