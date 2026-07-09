CREATE DATABASE IF NOT EXISTS authclaw;

CREATE TABLE IF NOT EXISTS authclaw.audit_events
(
    event_type LowCardinality(String),
    request_id String DEFAULT '',
    tenant_id String DEFAULT '',
    route_id String DEFAULT '',
    provider String DEFAULT '',
    model String DEFAULT '',
    risk_level LowCardinality(String) DEFAULT '',
    allowed UInt8 DEFAULT 0,
    status LowCardinality(String) DEFAULT '',
    decision LowCardinality(String) DEFAULT '',
    duration_ms UInt64 DEFAULT 0,
    latency UInt64 DEFAULT 0,
    tokens_in UInt64 DEFAULT 0,
    tokens_out UInt64 DEFAULT 0,
    record_id UInt64 DEFAULT 0,
    session_id String DEFAULT '',
    approval_id String DEFAULT '',
    username String DEFAULT '',
    approval_status LowCardinality(String) DEFAULT '',
    policy_name String DEFAULT '',
    policy_type LowCardinality(String) DEFAULT '',
    matched_pattern String DEFAULT '',
    integrity_hash String DEFAULT '',
    previous_hash String DEFAULT '',
    payload String DEFAULT '',
    created_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(created_at)
ORDER BY (tenant_id, created_at, event_type, request_id)
TTL created_at + INTERVAL 7 YEAR;

CREATE VIEW IF NOT EXISTS authclaw.gateway_metrics_view AS
SELECT
    tenant_id,
    request_id,
    route_id,
    provider,
    model,
    risk_level,
    allowed,
    decision,
    status,
    if(duration_ms > 0, duration_ms, latency) AS duration_ms,
    tokens_in,
    tokens_out,
    created_at
FROM authclaw.audit_events
WHERE event_type IN ('gateway_request', 'gateway_decision', 'request_completed');

CREATE VIEW IF NOT EXISTS authclaw.audit_ledger_view AS
SELECT
    tenant_id,
    record_id,
    event_type,
    integrity_hash,
    previous_hash,
    created_at
FROM authclaw.audit_events
WHERE integrity_hash != '';

CREATE TABLE IF NOT EXISTS authclaw.event_delivery_metrics
(
    stream LowCardinality(String),
    status LowCardinality(String),
    pending_events UInt64 DEFAULT 0,
    dead_letter_count UInt64 DEFAULT 0,
    lag_seconds UInt64 DEFAULT 0,
    max_attempts UInt64 DEFAULT 0,
    updated_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (stream, status);

CREATE VIEW IF NOT EXISTS authclaw.pipeline_health_view AS
SELECT
    stream,
    sum(pending_events) AS pending_events,
    sum(dead_letter_count) AS dead_letter_count,
    max(lag_seconds) AS max_lag_seconds,
    max(updated_at) AS last_updated_at
FROM authclaw.event_delivery_metrics
GROUP BY stream;
