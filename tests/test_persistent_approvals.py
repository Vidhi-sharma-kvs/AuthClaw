import hashlib
import uuid

from sqlalchemy import text

import approval_store
from approval_store import create_approval, get_approval
from database import engine
from main import API_KEY


def _tenant_id_for_test_key():
    key_hash = hashlib.sha256(API_KEY.encode("utf-8")).hexdigest()
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM tenant_api_keys WHERE key_hash = :hash"),
            {"hash": key_hash},
        ).scalar()


def test_approval_records_persist_and_reload_from_database():
    tenant_id = _tenant_id_for_test_key()
    request_id = f"req-persist-{uuid.uuid4().hex}"

    record = create_approval(
        query="delete production database",
        risk_level="HIGH",
        session_id=f"persist-{uuid.uuid4().hex}",
        tenant_id=tenant_id,
        request_id=request_id,
    )

    approval_id = record["approval_id"]
    approval_store._approvals.clear()

    reloaded = get_approval(approval_id)

    assert reloaded is not None
    assert reloaded["approval_id"] == approval_id
    assert reloaded["request_id"] == request_id
    assert reloaded["tenant_id"] == tenant_id
    assert reloaded["status"] == "pending"

    reloaded["status"] = "approved"
    approval_store._approvals.clear()

    approved = get_approval(approval_id)
    assert approved["status"] == "approved"
