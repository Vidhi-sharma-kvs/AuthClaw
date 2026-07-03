import pytest
from sqlalchemy import bindparam, text

from database import engine
from services.tenant_context import auth_lookup_context, tenant_context


def test_database_session_receives_tenant_and_request_context():
    with tenant_context(42, request_id="req-phase4", required=True), engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    current_setting('app.tenant_id', true),
                    current_setting('app.current_tenant_id', true),
                    current_setting('app.request_id', true),
                    current_setting('app.auth_lookup', true)
                """
            )
        ).fetchone()

    assert row[0] == "42"
    assert row[1] == "42"
    assert row[2] == "req-phase4"
    assert row[3] in ("", None)


def test_required_tenant_context_fails_closed_without_tenant():
    with pytest.raises(RuntimeError, match="Tenant context is required"):
        with tenant_context(None, request_id="req-missing-tenant", required=True), engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar()


def test_auth_lookup_context_is_explicit_and_does_not_set_tenant():
    with auth_lookup_context(), engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    current_setting('app.tenant_id', true),
                    current_setting('app.current_tenant_id', true),
                    current_setting('app.auth_lookup', true)
                """
            )
        ).fetchone()

    assert row[0] in ("", None)
    assert row[1] in ("", None)
    assert row[2] == "on"


def test_forced_rls_is_enabled_for_tenant_owned_tables():
    required_tables = {
        "audit_logs",
        "gateway_requests",
        "gateway_routes",
        "tenant_users",
        "tenant_api_keys",
        "tenant_credentials",
        "auth_refresh_tokens",
        "auth_mfa_sessions",
        "auth_password_reset_tokens",
        "documents",
        "document_findings",
        "chat_messages",
        "knowledge_documents",
        "knowledge_chunks",
        "policies",
    }

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT relname
                FROM pg_class
                WHERE relnamespace = 'public'::regnamespace
                  AND relname IN :tables
                  AND relrowsecurity = true
                  AND relforcerowsecurity = true
                """
            ).bindparams(bindparam("tables", expanding=True)),
            {"tables": list(required_tables)},
        ).fetchall()

    assert required_tables.issubset({row[0] for row in rows})
