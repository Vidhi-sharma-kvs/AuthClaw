import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import conftest
from database import engine
from main import _consume_rate_limit_token, app, create_jwt
from services.event_pipeline import EventPipeline
from services.worker_throttle import WorkerThrottle


client = TestClient(app)


def _headers():
    token = create_jwt(
        {
            "sub": conftest.tenant_email,
            "email": conftest.tenant_email,
            "tenant_id": conftest.tenant_id,
            "role": "Super Admin",
        }
    )
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test_phase8_event_pipeline_records_delivery_and_metrics(monkeypatch):
    monkeypatch.delenv("KAFKA_REST_URL", raising=False)
    monkeypatch.delenv("CLICKHOUSE_HTTP_URL", raising=False)
    monkeypatch.delenv("AUTHCLAW_REQUIRE_KAFKA", raising=False)
    event_id = f"phase8-{uuid.uuid4()}"

    result = EventPipeline().record_and_deliver(
        {
            "event_type": "gateway_request",
            "request_id": event_id,
            "tenant_id": conftest.tenant_id,
            "allowed": True,
            "status": "allowed",
            "duration_ms": 31,
        },
        stream="audit",
    )

    assert result["status"] == "delivered"
    metrics = EventPipeline().delivery_metrics()
    assert metrics["streams"]["audit"]["delivered"] >= 1
    assert metrics["checkpoints"]

    response = client.get("/analytics/governance", headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert "event_pipeline" in body
    assert "queue_lag" in body
    assert body["queue_lag"]["dead_letter_count"] >= 0


def test_phase8_event_pipeline_dead_letters_when_required_kafka_missing(monkeypatch):
    monkeypatch.delenv("KAFKA_REST_URL", raising=False)
    monkeypatch.setenv("AUTHCLAW_REQUIRE_KAFKA", "true")
    event_id = f"phase8-dlq-{uuid.uuid4()}"

    result = EventPipeline().record_and_deliver(
        {
            "event_type": "gateway_request",
            "request_id": event_id,
            "tenant_id": conftest.tenant_id,
            "allowed": False,
            "status": "blocked",
        },
        stream="audit",
    )

    assert result["status"] == "dead_letter"
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, attempts FROM event_delivery_records WHERE event_id = :event_id"),
            {"event_id": f"gateway_request:{event_id}"},
        ).fetchone()
        dlq_count = conn.execute(
            text("SELECT COUNT(*) FROM event_dead_letters WHERE event_id = :event_id"),
            {"event_id": f"gateway_request:{event_id}"},
        ).scalar()
    assert row.status == "dead_letter"
    assert row.attempts >= 1
    assert dlq_count == 1


def test_phase8_rate_limit_and_worker_throttle_are_recorded(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    allowed, remaining, backend = _consume_rate_limit_token(conftest.tenant_id, 1)
    assert allowed is True
    assert remaining == 0
    assert backend == "memory"

    WorkerThrottle("remediation").check(conftest.tenant_id)

    with engine.connect() as conn:
        limiter_count = conn.execute(
            text("SELECT COUNT(*) FROM rate_limit_events WHERE tenant_id = :tenant_id"),
            {"tenant_id": conftest.tenant_id},
        ).scalar()
        throttle_count = conn.execute(
            text("SELECT COUNT(*) FROM worker_throttle_events WHERE tenant_id = :tenant_id"),
            {"tenant_id": conftest.tenant_id},
        ).scalar()
    assert limiter_count >= 1
    assert throttle_count >= 1

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    body = metrics.json()
    assert "event_pipeline" in body
    assert "queue_lag_seconds" in body
    assert "rate_limit_blocked" in body
    assert "worker_throttle_blocked" in body


def test_phase8_worker_throttle_rejects_when_limit_exceeded(monkeypatch):
    monkeypatch.setenv("AUTHCLAW_REMEDIATION_WORKER_LIMIT", "0")
    throttle = WorkerThrottle("remediation")
    with pytest.raises(RuntimeError):
        throttle.enforce(conftest.tenant_id)
