import hashlib

from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import app, create_jwt, encrypt_secret


client = TestClient(app)


def _create_tenant(name: str) -> int:
    with engine.connect() as conn:
        tenant_id = conn.execute(
            text(
                """
                INSERT INTO tenants (name, domain, email, email_verified, domain_verified)
                VALUES (:name, :domain, :email, true, true)
                RETURNING id
                """
            ),
            {
                "name": name,
                "domain": f"{name.lower()}.example",
                "email": f"admin@{name.lower()}.example",
            },
        ).scalar()
        conn.commit()
    return tenant_id


def _auth_header(tenant_id: int) -> dict:
    token = create_jwt({"sub": f"admin-{tenant_id}", "tenant_id": tenant_id, "user_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


def _insert_document_bundle(tenant_id: int, filename: str) -> tuple[int, int]:
    with engine.connect() as conn:
        doc_id = conn.execute(
            text(
                """
                INSERT INTO documents (tenant_id, filename, source, status, size_bytes, risk_score, severity)
                VALUES (:tenant_id, :filename, 'pytest', 'completed', 128, 10, 'LOW')
                RETURNING id
                """
            ),
            {"tenant_id": tenant_id, "filename": filename},
        ).scalar()
        conn.execute(
            text(
                """
                INSERT INTO document_findings (
                    tenant_id, document_id, finding_type, matched_pattern,
                    matched_text, risk_level, recommendation
                )
                VALUES (
                    :tenant_id, :document_id, 'PII', 'EMAIL',
                    'hidden@example.com', 'LOW', 'Redact email.'
                )
                """
            ),
            {"tenant_id": tenant_id, "document_id": doc_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO document_audits (
                    tenant_id, document_id, action, actor, details,
                    integrity_hash, previous_hash
                )
                VALUES (
                    :tenant_id, :document_id, 'created', 'pytest', 'tenant isolation fixture',
                    :hash, :previous_hash
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "document_id": doc_id,
                "hash": hashlib.sha256(f"{tenant_id}-{doc_id}".encode()).hexdigest(),
                "previous_hash": "0" * 64,
            },
        )
        k_doc_id = conn.execute(
            text(
                """
                INSERT INTO knowledge_documents (
                    tenant_id, name, type, size_bytes, status, last_indexed, chunks_count
                )
                VALUES (:tenant_id, :filename, 'TXT', 128, 'indexed', '2026-01-01', 1)
                RETURNING id
                """
            ),
            {"tenant_id": tenant_id, "filename": filename},
        ).scalar()
        conn.execute(
            text(
                """
                INSERT INTO knowledge_chunks (
                    tenant_id, document_id, content, embedding_preview, embedding_vector
                )
                VALUES (:tenant_id, :document_id, :content, '[0.1, 0.2, ...]', '[0.1, 0.2, 0.3]')
                """
            ),
            {
                "tenant_id": tenant_id,
                "document_id": k_doc_id,
                "content": f"Private tenant {tenant_id} document content.",
            },
        )
        conn.commit()
    return doc_id, k_doc_id


def test_document_and_rag_resources_are_tenant_isolated():
    tenant_a = _create_tenant("DocIsoA")
    tenant_b = _create_tenant("DocIsoB")
    doc_a, k_doc_a = _insert_document_bundle(tenant_a, "tenant-a-policy.txt")
    doc_b, k_doc_b = _insert_document_bundle(tenant_b, "tenant-b-policy.txt")

    try:
        documents_a = client.get("/documents", headers=_auth_header(tenant_a))
        assert documents_a.status_code == 200
        visible_doc_ids = {item["id"] for item in documents_a.json()}
        assert doc_a in visible_doc_ids
        assert doc_b not in visible_doc_ids

        assert client.get(f"/documents/{doc_b}", headers=_auth_header(tenant_a)).status_code == 404
        assert client.get(f"/documents/{doc_b}/findings", headers=_auth_header(tenant_a)).status_code == 404
        assert client.get(f"/documents/{doc_b}/audit", headers=_auth_header(tenant_a)).status_code == 404

        rag_docs_a = client.get("/rag/documents", headers=_auth_header(tenant_a))
        assert rag_docs_a.status_code == 200
        visible_rag_ids = {item["id"] for item in rag_docs_a.json()}
        assert k_doc_a in visible_rag_ids
        assert k_doc_b not in visible_rag_ids
        assert client.get(f"/rag/chunks/{k_doc_b}", headers=_auth_header(tenant_a)).status_code == 404
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM tenants WHERE id IN (:tenant_a, :tenant_b)"), {"tenant_a": tenant_a, "tenant_b": tenant_b})
            conn.commit()


def test_gateway_requests_and_provider_credentials_are_tenant_isolated():
    tenant_a = _create_tenant("RuntimeIsoA")
    tenant_b = _create_tenant("RuntimeIsoB")

    with engine.connect() as conn:
        conn.execute(
            text(
                """
                INSERT INTO gateway_requests (
                    timestamp, risk_level, allowed, status, request_id,
                    tenant_id, provider, model, decision
                )
                VALUES
                    (NOW(), 'LOW', true, 'allowed', 'req-tenant-a', :tenant_a, 'openai', 'gpt-4o', 'ALLOW'),
                    (NOW(), 'LOW', true, 'allowed', 'req-tenant-b', :tenant_b, 'gemini', 'gemini-2.5-flash-lite', 'ALLOW')
                """
            ),
            {"tenant_a": str(tenant_a), "tenant_b": str(tenant_b)},
        )
        conn.execute(
            text(
                """
                INSERT INTO tenant_credentials (tenant_id, provider, encrypted_payload)
                VALUES
                    (:tenant_a, 'openai', :payload_a),
                    (:tenant_b, 'gemini', :payload_b)
                """
            ),
            {
                "tenant_a": tenant_a,
                "tenant_b": tenant_b,
                "payload_a": encrypt_secret('{"api_key":"tenant-a"}'),
                "payload_b": encrypt_secret('{"api_key":"tenant-b"}'),
            },
        )
        conn.commit()

    try:
        requests_a = client.get("/gateway/requests", headers=_auth_header(tenant_a))
        assert requests_a.status_code == 200
        visible_request_ids = {item["request_id"] for item in requests_a.json()}
        assert "req-tenant-a" in visible_request_ids
        assert "req-tenant-b" not in visible_request_ids
        assert client.get("/gateway/requests/req-tenant-b", headers=_auth_header(tenant_a)).status_code == 404

        providers_a = client.get("/providers/list", headers=_auth_header(tenant_a))
        assert providers_a.status_code == 200
        provider_names = {item["provider"] for item in providers_a.json()}
        assert "openai" in provider_names
        assert "gemini" not in provider_names
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM tenants WHERE id IN (:tenant_a, :tenant_b)"), {"tenant_a": tenant_a, "tenant_b": tenant_b})
            conn.commit()


def test_postgresql_rls_policies_exist_for_tenant_tables():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT tablename
                FROM pg_policies
                WHERE schemaname = 'public'
                  AND policyname LIKE 'tenant_isolation_%'
                  AND tablename IN (
                    'documents', 'document_findings', 'document_audits',
                    'knowledge_documents', 'knowledge_chunks',
                    'tenant_api_keys', 'tenant_credentials', 'audit_logs'
                  )
                """
            )
        ).fetchall()

    assert {
        "documents",
        "document_findings",
        "document_audits",
        "knowledge_documents",
        "knowledge_chunks",
        "tenant_api_keys",
        "tenant_credentials",
        "audit_logs",
    }.issubset({row[0] for row in rows})
