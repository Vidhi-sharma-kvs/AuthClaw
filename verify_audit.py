import hashlib
import json
import contextvars
from datetime import datetime
from sqlalchemy import text
from database import engine

GENESIS_HASH = "0" * 64
_agent_event_request_id = contextvars.ContextVar("agent_event_request_id", default=None)
_agent_event_sequence = contextvars.ContextVar("agent_event_sequence", default=0)


def set_agent_event_context(request_id: str):
    request_token = _agent_event_request_id.set(request_id)
    sequence_token = _agent_event_sequence.set(0)
    return request_token, sequence_token


def clear_agent_event_context(token) -> None:
    if not token:
        return
    request_token, sequence_token = token
    _agent_event_sequence.reset(sequence_token)
    _agent_event_request_id.reset(request_token)

def calculate_record_hash(record: dict, previous_hash: str) -> str:
    """
    Deterministically computes the SHA-256 integrity hash for a single audit log record.
    Hashed fields: record_id, user_query, response, allowed, created_at, risk_level, approval_status, previous_hash
    """
    # format created_at to a standardized string representation
    created_at = record["created_at"]
    if hasattr(created_at, "isoformat"):
        created_at_str = created_at.isoformat()
    else:
        created_at_str = str(created_at)

    hash_data = {
        "record_id": int(record["record_id"]),
        "user_query": record["user_query"] or "",
        "response": record["response"] or "",
        "allowed": bool(record["allowed"]),
        "created_at": created_at_str,
        "risk_level": record["risk_level"] or "",
        "approval_status": record["approval_status"] or "",
        "previous_hash": previous_hash
    }
    
    serialized = json.dumps(hash_data, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_audit_chain(tenant_id: int = None) -> dict:
    """
    Performs full integrity check on the audit log cryptographic chain:
    - Recalculates hashes.
    - Verifies previous_hash linkage.
    - Detects modified records.
    - Detects deleted records and missing ID gaps.
    - Detects broken chain continuity.
    """
    with engine.connect() as conn:
        params = {}
        tenant_filter = ""
        if tenant_id is not None:
            tenant_filter = "WHERE tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        res = conn.execute(
            text(f"""
            SELECT id, user_query, response, allowed, created_at, risk_level, approval_status, integrity_hash, previous_hash
            FROM audit_logs
            {tenant_filter}
            ORDER BY id ASC
            """),
            params
        )
        rows = res.fetchall()

    if not rows:
        return {
            "valid": True,
            "records_checked": 0,
            "chain_started_at": None
        }

    # Identify the start of the cryptographic chain (the first record with a non-null hash)
    start_index = -1
    for i, r in enumerate(rows):
        if r[7] is not None:  # integrity_hash is not None
            start_index = i
            break

    if start_index == -1:
        # No chained records exist yet (all are legacy)
        return {
            "valid": True,
            "records_checked": 0,
            "chain_started_at": None
        }

    records_checked = 0
    chain_started_at = rows[start_index][4]
    if hasattr(chain_started_at, "isoformat"):
        chain_started_at_str = chain_started_at.isoformat()
    else:
        chain_started_at_str = str(chain_started_at)

    prev_id = None
    prev_hash = None

    for i in range(start_index, len(rows)):
        r = rows[i]
        rec_id = r[0]
        query = r[1]
        response = r[2]
        allowed = r[3]
        created_at = r[4]
        risk_level = r[5]
        approval_status = r[6]
        integrity_hash = r[7]
        previous_hash = r[8]

        # Verify hash columns are present once the chain starts
        if integrity_hash is None or previous_hash is None:
            return {
                "valid": False,
                "records_checked": records_checked,
                "failed_record_id": rec_id,
                "reason": "missing hash metadata in active chain"
            }

        # 1. Detect ID gaps (deleted records)
        if tenant_id is None and prev_id is not None:
            if rec_id != prev_id + 1:
                return {
                    "valid": False,
                    "records_checked": records_checked,
                    "failed_record_id": rec_id,
                    "reason": f"missing record detected between {prev_id} and {rec_id}"
                }

        # 2. Verify previous_hash linkage
        expected_prev = GENESIS_HASH if prev_hash is None else prev_hash
        if previous_hash != expected_prev:
            return {
                "valid": False,
                "records_checked": records_checked,
                "failed_record_id": rec_id,
                "reason": "broken link"
            }

        # 3. Recalculate hash to verify against tampering (modification)
        record_dict = {
            "record_id": rec_id,
            "user_query": query,
            "response": response,
            "allowed": allowed,
            "created_at": created_at,
            "risk_level": risk_level,
            "approval_status": approval_status
        }
        computed_hash = calculate_record_hash(record_dict, previous_hash)
        if integrity_hash != computed_hash:
            return {
                "valid": False,
                "records_checked": records_checked,
                "failed_record_id": rec_id,
                "reason": "hash mismatch"
            }

        prev_id = rec_id
        prev_hash = integrity_hash
        records_checked += 1

    return {
        "valid": True,
        "records_checked": records_checked,
        "chain_started_at": chain_started_at_str
    }

def record_gateway_request(
    risk_level: str,
    allowed: bool,
    status: str,
    request_id: str = None,
    tenant_id: str = "Default Tenant",
    route_id: str = None,
    provider: str = "OpenAI",
    model: str = "gpt-4o",
    latency: int = 150,
    tokens_in: int = 0,
    tokens_out: int = 0,
    decision: str = None,
    duration_ms: int = None
):
    """
    Centrally and persistently records every incoming gateway request to PostgreSQL.
    """
    from database import engine
    from datetime import datetime
    import uuid
    try:
        if not request_id:
            request_id = f"req-{uuid.uuid4()}"
        with engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO gateway_requests (
                    timestamp, created_at, risk_level, allowed, status, request_id, 
                    tenant_id, route_id, provider, model, latency, 
                    tokens_in, tokens_out, decision, duration_ms
                )
                VALUES (
                    :timestamp, :created_at, :risk_level, :allowed, :status, :request_id, 
                    :tenant_id, :route_id, :provider, :model, :latency, 
                    :tokens_in, :tokens_out, :decision, :duration_ms
                )
                """),
                {
                    "timestamp": datetime.now(),
                    "created_at": datetime.now(),
                    "risk_level": risk_level,
                    "allowed": allowed,
                    "status": status,
                    "request_id": request_id,
                    "tenant_id": tenant_id,
                    "route_id": route_id or "1",
                    "provider": provider,
                    "model": model,
                    "latency": latency,
                    "tokens_in": tokens_in or int(len(risk_level) * 15),
                    "tokens_out": tokens_out or int(len(status) * 25),
                    "decision": decision,
                    "duration_ms": duration_ms if duration_ms is not None else latency
                }
            )
            conn.commit()
    except Exception as e:
        print(f"Error logging gateway request metrics: {e}", flush=True)

def create_audit_block(
    query: str,
    response: str,
    allowed: bool,
    risk_level: str,
    approval_status: str,
    session_id: str = "N/A",
    approval_id: str = None,
    approver: str = None,
    original_request: str = None,
    approval_timestamp: datetime = None,
    execution_timestamp: datetime = None,
    execution_status: str = None,
    policy_name: str = None,
    policy_type: str = None,
    matched_pattern: str = None,
    redacted_value: str = None,
    username: str = None,
    tenant_id: int = None
) -> int:
    """
    Creates a new cryptographic audit block in PostgreSQL database and recalculates hashes.
    """
    from database import engine
    from startup.audit import log_audit_event
    from datetime import datetime
    
    with engine.connect() as conn:
        res = conn.execute(
            text("""
            INSERT INTO audit_logs
            (
                user_query,
                response,
                allowed,
                risk_level,
                approval_status,
                created_at,
                approval_id,
                approver,
                original_request,
                approval_timestamp,
                execution_timestamp,
                execution_status,
                policy_name,
                policy_type,
                matched_pattern,
                redacted_value,
                username,
                tenant_id
            )
            VALUES
            (
                :query,
                :response,
                :allowed,
                :risk_level,
                :approval_status,
                :created_at,
                :approval_id,
                :approver,
                :original_request,
                :approval_timestamp,
                :execution_timestamp,
                :execution_status,
                :policy_name,
                :policy_type,
                :matched_pattern,
                :redacted_value,
                :username,
                :tenant_id
            )
            RETURNING id, created_at
            """),
            {
                "query": query,
                "response": response,
                "allowed": allowed,
                "risk_level": risk_level,
                "approval_status": approval_status,
                "created_at": datetime.now(),
                "approval_id": approval_id,
                "approver": approver,
                "original_request": original_request or query,
                "approval_timestamp": approval_timestamp,
                "execution_timestamp": execution_timestamp,
                "execution_status": execution_status,
                "policy_name": policy_name,
                "policy_type": policy_type,
                "matched_pattern": matched_pattern,
                "redacted_value": redacted_value,
                "username": username,
                "tenant_id": tenant_id
            }
        )
        row = res.fetchone()
        inserted_id = row[0]
        db_created_at = row[1]
        conn.commit()

        # Retrieve the integrity_hash of the latest record before the newly inserted one
        prev_res = conn.execute(
            text("""
            SELECT integrity_hash
            FROM audit_logs
            WHERE id < :inserted_id
              AND integrity_hash IS NOT NULL
              AND (
                (:tenant_id IS NULL AND tenant_id IS NULL)
                OR tenant_id = :tenant_id
              )
            ORDER BY id DESC
            LIMIT 1
            """),
            {"inserted_id": inserted_id, "tenant_id": tenant_id}
        ).fetchone()
        previous_hash = prev_res[0] if prev_res else GENESIS_HASH

        # Calculate current record hash
        record_dict = {
            "record_id": inserted_id,
            "user_query": query,
            "response": response,
            "allowed": allowed,
            "created_at": db_created_at,
            "risk_level": risk_level,
            "approval_status": approval_status,
        }
        current_hash = calculate_record_hash(record_dict, previous_hash)

        # Update the record with calculated hashes
        conn.execute(
            text("""
            UPDATE audit_logs
            SET integrity_hash = :integrity_hash, previous_hash = :previous_hash
            WHERE id = :id
            """),
            {
                "integrity_hash": current_hash,
                "previous_hash": previous_hash,
                "id": inserted_id
            }
        )
        conn.commit()

        # Log audit chain created event
        log_audit_event(
            event="audit_chain_created",
            correlation_id=session_id,
            extra={
                "record_id": inserted_id,
                "integrity_hash": current_hash,
                "previous_hash": previous_hash
            }
        )
        return inserted_id

def log_agent_event(
    tenant_id: int,
    session_id: str,
    agent_name: str,
    event_type: str,
    details: str,
    request_id: str = None,
    sequence: int = None
):
    """
    Logs an agent execution event dynamically to the database.
    """
    from database import engine
    from sqlalchemy import text
    try:
        effective_request_id = request_id or _agent_event_request_id.get()
        effective_sequence = sequence
        if effective_sequence is None and effective_request_id:
            current_sequence = _agent_event_sequence.get()
            effective_sequence = current_sequence + 1
            _agent_event_sequence.set(effective_sequence)

        with engine.connect() as conn:
            conn.execute(
                text("""
                INSERT INTO agent_events (tenant_id, session_id, request_id, sequence, agent_name, event_type, details)
                VALUES (:tid, :sid, :rid, :seq, :agent, :type, :details)
                """),
                {
                    "tid": tenant_id,
                    "sid": session_id,
                    "rid": effective_request_id,
                    "seq": effective_sequence,
                    "agent": agent_name,
                    "type": event_type,
                    "details": details
                }
            )
            conn.commit()
    except Exception as e:
        import logging
        logger = logging.getLogger("authclaw.agent_events")
        logger.error(f"Failed to log agent event: {e}", exc_info=True)
