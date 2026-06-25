"""
approval_store.py — In-memory approval store for the HITL workflow.

Stores rich approval metadata including status, timestamps, MFA tracking,
correlation IDs, and expiry windows. Expiration is checked lazily on every
read/list access so no background thread is needed.

Backward-compatible: `pending_approvals` and `approved_results` aliases are
kept so existing imports in main.py continue to work during the transition.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import text

from database import engine


# ── Internal store ──────────────────────────────────────────────────────────
# Single source of truth for ALL approvals regardless of status.
_approvals: Dict[str, dict] = {}

# Default expiry window (minutes). Overridden at runtime by policy.
DEFAULT_EXPIRY_MINUTES: int = 30


class PersistentApprovalRecord(dict):
    def __init__(self, *args, persist_enabled: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self._persist_enabled = persist_enabled

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        if getattr(self, "_persist_enabled", False):
            _persist_record(self)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_optional_dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


def _expiry_minutes() -> int:
    """Pull expiry_minutes from the live policy cache; fall back to default."""
    try:
        from policy import get_policy
        return get_policy().get("approval", {}).get("expiry_minutes", DEFAULT_EXPIRY_MINUTES)
    except Exception:
        return DEFAULT_EXPIRY_MINUTES


def _check_expiry(record: dict) -> dict:
    """
    If a 'pending' record has passed its expires_at, mutate status to 'expired'
    in-place and return the (now-mutated) record.
    """
    if record["status"] == "pending":
        expires_at = datetime.fromisoformat(record["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= expires_at:
            record["status"] = "expired"
            _persist_record(record)
            # Emit audit event lazily — import here to avoid circular deps
            try:
                from startup.audit import log_approval_event
                log_approval_event(
                    event="approval_expired",
                    approval_id=record["approval_id"],
                    request_id=record["request_id"],
                    correlation_id=record["correlation_id"],
                    extra={"expires_at": record["expires_at"]},
                )
            except Exception:
                pass
    return record


def _persist_record(record: dict) -> None:
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO gateway_approvals (
                        approval_id, request_id, correlation_id, tenant_id, status,
                        created_at, expires_at, approved_at, rejected_at, executed_at,
                        requested_action, query, risk_level, audit_id, metadata
                    )
                    VALUES (
                        :approval_id, :request_id, :correlation_id, :tenant_id, :status,
                        :created_at, :expires_at, :approved_at, :rejected_at, :executed_at,
                        :requested_action, :query, :risk_level, :audit_id, :metadata
                    )
                    ON CONFLICT (approval_id) DO UPDATE SET
                        request_id = EXCLUDED.request_id,
                        correlation_id = EXCLUDED.correlation_id,
                        tenant_id = EXCLUDED.tenant_id,
                        status = EXCLUDED.status,
                        expires_at = EXCLUDED.expires_at,
                        approved_at = EXCLUDED.approved_at,
                        rejected_at = EXCLUDED.rejected_at,
                        executed_at = EXCLUDED.executed_at,
                        requested_action = EXCLUDED.requested_action,
                        query = EXCLUDED.query,
                        risk_level = EXCLUDED.risk_level,
                        audit_id = EXCLUDED.audit_id,
                        metadata = EXCLUDED.metadata
                    """
                ),
                {
                    "approval_id": record.get("approval_id"),
                    "request_id": record.get("request_id"),
                    "correlation_id": record.get("correlation_id"),
                    "tenant_id": record.get("tenant_id"),
                    "status": record.get("status"),
                    "created_at": _parse_optional_dt(record.get("created_at")),
                    "expires_at": _parse_optional_dt(record.get("expires_at")),
                    "approved_at": _parse_optional_dt(record.get("approved_at")),
                    "rejected_at": _parse_optional_dt(record.get("rejected_at")),
                    "executed_at": _parse_optional_dt(record.get("executed_at")),
                    "requested_action": record.get("requested_action"),
                    "query": record.get("query"),
                    "risk_level": record.get("risk_level"),
                    "audit_id": record.get("audit_id"),
                    "metadata": json.dumps(record.get("metadata", {})),
                },
            )
            conn.commit()
    except Exception:
        pass


def _row_to_record(row) -> PersistentApprovalRecord:
    mapping = dict(row._mapping)

    def as_iso(value):
        if value is None:
            return None
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    return PersistentApprovalRecord(
        {
            "approval_id": mapping.get("approval_id"),
            "request_id": mapping.get("request_id"),
            "correlation_id": mapping.get("correlation_id"),
            "tenant_id": mapping.get("tenant_id"),
            "status": mapping.get("status"),
            "created_at": as_iso(mapping.get("created_at")),
            "expires_at": as_iso(mapping.get("expires_at")),
            "approved_at": as_iso(mapping.get("approved_at")),
            "rejected_at": as_iso(mapping.get("rejected_at")),
            "executed_at": as_iso(mapping.get("executed_at")),
            "requested_action": mapping.get("requested_action"),
            "query": mapping.get("query"),
            "risk_level": mapping.get("risk_level"),
            "audit_id": mapping.get("audit_id"),
            "metadata": json.loads(mapping.get("metadata") or "{}"),
        }
    )


def _load_record(approval_id: str) -> Optional[PersistentApprovalRecord]:
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT * FROM gateway_approvals WHERE approval_id = :approval_id"),
                {"approval_id": approval_id},
            ).fetchone()
        return _row_to_record(row) if row else None
    except Exception:
        return None


def _load_all_records() -> None:
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT * FROM gateway_approvals ORDER BY created_at DESC")).fetchall()
        for row in rows:
            record = _row_to_record(row)
            _approvals[record["approval_id"]] = record
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def create_approval(
    query: str,
    risk_level: str,
    session_id: str = "",
    tenant_id: int = None,
    request_id: str = None,
) -> dict:
    """
    Creates a new approval record, stores it, and returns it.
    Emits an approval_created audit event.
    """
    approval_id = str(uuid.uuid4())
    request_id = request_id or str(uuid.uuid4())
    correlation_id = session_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=_expiry_minutes())

    record = PersistentApprovalRecord({
        "approval_id":       approval_id,
        "request_id":        request_id,
        "correlation_id":    correlation_id,
        "tenant_id":         tenant_id,
        "status":            "pending",
        "created_at":        now.isoformat(),
        "expires_at":        expires_at.isoformat(),
        "approved_at":       None,
        "rejected_at":       None,
        "executed_at":       None,
        "requested_action":  query,
        "query":             query,
        "risk_level":        risk_level,
        "audit_id":          None,
        "metadata":          {},
    })
    _approvals[approval_id] = record
    _persist_record(record)

    try:
        from startup.audit import log_approval_event
        log_approval_event(
            event="approval_created",
            approval_id=approval_id,
            request_id=request_id,
            correlation_id=correlation_id,
            extra={"risk_level": risk_level, "expires_at": expires_at.isoformat()},
        )
    except Exception:
        pass



    return record


def get_approval(approval_id: str) -> Optional[dict]:
    """
    Returns the approval record (or None if not found).
    Lazily marks pending records as expired.
    """
    record = _approvals.get(approval_id)
    if record is None:
        record = _load_record(approval_id)
        if record is None:
            return None
        _approvals[approval_id] = record
    return _check_expiry(record)


def get_all_approvals() -> Dict[str, dict]:
    """
    Returns all approval records as a dict keyed by approval_id.
    Lazily marks any expired pending records.
    """
    _load_all_records()
    for record in _approvals.values():
        _check_expiry(record)
    return _approvals


def remaining_seconds(record: dict) -> int:
    """Returns seconds left before expiry (0 if already expired/approved/rejected)."""
    if record["status"] != "pending":
        return 0
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    delta = (expires_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


# ── Backward-compatible aliases ───────────────────────────────────────────────
# These provide dict-like read access to the underlying store so that any
# existing code using `pending_approvals[id]` or `approved_results[id]` keeps
# working without modification.

class _PendingView:
    """Read-only dict-like view of pending approvals (lazy expiry applied)."""

    def __contains__(self, approval_id):
        record = get_approval(approval_id)
        return record is not None and record["status"] == "pending"

    def __getitem__(self, approval_id):
        record = get_approval(approval_id)
        if record is None or record["status"] != "pending":
            raise KeyError(approval_id)
        return record

    def __iter__(self):
        return (
            aid for aid, r in get_all_approvals().items()
            if r["status"] == "pending"
        )

    def items(self):
        return [
            (aid, r) for aid, r in get_all_approvals().items()
            if r["status"] == "pending"
        ]


class _ApprovedView:
    """Read-only dict-like view of approved approvals."""

    def __contains__(self, approval_id):
        record = get_approval(approval_id)
        return record is not None and record["status"] == "approved"

    def __getitem__(self, approval_id):
        record = get_approval(approval_id)
        if record is None or record["status"] != "approved":
            raise KeyError(approval_id)
        return record

    def __iter__(self):
        return (
            aid for aid, r in get_all_approvals().items()
            if r["status"] == "approved"
        )

    def items(self):
        return [
            (aid, r) for aid, r in get_all_approvals().items()
            if r["status"] == "approved"
        ]


pending_approvals = _PendingView()
approved_results  = _ApprovedView()
