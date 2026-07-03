from fastapi.testclient import TestClient
from sqlalchemy import text

from database import engine
from main import app, create_jwt


client = TestClient(app)


def _tenant(name: str) -> int:
    with engine.connect() as conn:
        row = conn.execute(
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
        ).fetchone()
        conn.commit()
    return row[0]


def _auth_header(tenant_id: int) -> dict:
    token = create_jwt({"sub": f"admin-{tenant_id}", "tenant_id": tenant_id, "user_id": tenant_id})
    return {"Authorization": f"Bearer {token}"}


def test_gateway_routes_are_visible_only_to_owning_tenant():
    tenant_a = _tenant("RouteIsoA")
    tenant_b = _tenant("RouteIsoB")

    with engine.connect() as conn:
        route_id = conn.execute(
            text(
                """
                INSERT INTO gateway_routes (
                    tenant_id, name, provider, endpoint, model, rate_limit,
                    redaction_enabled, enabled, tenant_assignment
                )
                VALUES (:tenant_id, 'tenant-a-route', 'openai', 'https://example.invalid/v1',
                        'gpt-4o-mini', 100, true, true, :assignment)
                RETURNING id
                """
            ),
            {"tenant_id": tenant_a, "assignment": str(tenant_a)},
        ).fetchone()[0]
        conn.commit()

    try:
        own_response = client.get("/routes", headers=_auth_header(tenant_a))
        other_response = client.get("/routes", headers=_auth_header(tenant_b))

        assert own_response.status_code == 200
        assert other_response.status_code == 200
        assert route_id in [route["id"] for route in own_response.json()]
        assert route_id not in [route["id"] for route in other_response.json()]
    finally:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM gateway_routes WHERE id = :id"), {"id": route_id})
            conn.execute(text("DELETE FROM tenants WHERE id IN (:tenant_a, :tenant_b)"), {"tenant_a": tenant_a, "tenant_b": tenant_b})
            conn.commit()
