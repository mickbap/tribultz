"""PostgresTool – reusable DB operations for agents and tasks."""

import json
from datetime import date
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import SessionLocal


def _session() -> Session:
    return SessionLocal()


_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type        VARCHAR(100) NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'QUEUED',
    idempotency_key VARCHAR(200),
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status);
"""


def _ensure_jobs_table(db: Session) -> None:
    db.execute(text(_JOBS_DDL))
    db.commit()


# ── 1. Audit Log ──────────────────────────────────────────────
def insert_audit_log(
    tenant_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    payload: Optional[dict] = None,
) -> dict:
    """
    Insert an audit-log row and return {id, checksum}.
    The checksum is a SHA-256 of the payload for tamper-evidence.
    """
    from hashlib import sha256

    payload = payload or {}
    checksum = sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    payload["_checksum"] = checksum

    audit_id = str(uuid4())
    payload_json = json.dumps(payload, default=str)

    db = _session()
    try:
        db.execute(
            text("""
                INSERT INTO audit_log
                    (id, tenant_id, user_id, action, entity_type, entity_id, payload)
                VALUES
                    (CAST(:id AS uuid), CAST(:tid AS uuid),
                     CAST(:uid AS uuid), :action, :etype, :eid,
                     CAST(:payload AS jsonb))
            """),
            {
                "id": audit_id,
                "tid": tenant_id,
                "uid": user_id,
                "action": action,
                "etype": entity_type,
                "eid": entity_id,
                "payload": payload_json,
            },
        )
        db.commit()
    finally:
        db.close()

    return {"id": audit_id, "checksum": checksum}


# ── 2. Tax Rules ──────────────────────────────────────────────
def get_tax_rules(
    tenant_id: str,
    codes: list[str],
    ref_date: Optional[date] = None,
) -> list[dict]:
    """
    Return active tax rules for the given tenant and rule_codes.
    If ref_date is omitted, uses today.
    """
    ref = ref_date or date.today()
    db = _session()
    try:
        placeholders = ", ".join(f":code_{i}" for i in range(len(codes)))
        params: dict[str, Any] = {"tid": tenant_id, "ref": ref}
        for i, c in enumerate(codes):
            params[f"code_{i}"] = c

        rows = db.execute(
            text(f"""
                SELECT rule_code, description, tax_type, rate,
                       valid_from, valid_to
                FROM tax_rules
                WHERE tenant_id = CAST(:tid AS uuid)
                  AND rule_code IN ({placeholders})
                  AND valid_from <= :ref
                  AND (valid_to IS NULL OR valid_to >= :ref)
                ORDER BY tax_type, valid_from DESC
            """),
            params,
        ).fetchall()

        return [
            {
                "rule_code": r.rule_code,
                "description": r.description,
                "tax_type": r.tax_type,
                "rate": float(r.rate),
                "valid_from": r.valid_from.isoformat(),
                "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            }
            for r in rows
        ]
    finally:
        db.close()


# ── 3. Artifact Metadata ─────────────────────────────────────
def persist_artifact_metadata(
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    artifact_type: str,
    storage_key: str,
    checksum: str,
    metadata: Optional[dict] = None,
) -> dict:
    """
    Persist metadata about a produced artifact (PDF, XML, report)
    into the audit_log so everything is traceable.
    """
    payload = {
        "artifact_type": artifact_type,
        "storage_key": storage_key,
        "checksum": checksum,
        **(metadata or {}),
    }
    return insert_audit_log(
        tenant_id=tenant_id,
        action="artifact_created",
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )


# ── 4. Job Status Update ─────────────────────────────────────
def get_tenant_slug(tenant_id: str) -> str:
    """Resolve tenant slug from tenant UUID string."""
    db = _session()
    try:
        row = db.execute(
            text("SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)"),
            {"id": tenant_id},
        ).fetchone()
        if not row:
            raise ValueError(f"Tenant not found for id={tenant_id}")
        return str(row.slug)
    finally:
        db.close()


def job_create(
    *,
    job_id: str,
    tenant_id: str,
    job_type: str,
    payload: Optional[dict] = None,
    idempotency_key: Optional[str] = None,
) -> dict:
    """Create a QUEUED job row with a deterministic job_id."""
    db = _session()
    try:
        _ensure_jobs_table(db)
        db.execute(
            text(
                """
                INSERT INTO jobs (id, tenant_id, job_type, status, idempotency_key, payload)
                VALUES (
                    CAST(:id AS uuid),
                    CAST(:tenant_id AS uuid),
                    :job_type,
                    'QUEUED',
                    :idempotency_key,
                    CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "id": job_id,
                "tenant_id": tenant_id,
                "job_type": job_type,
                "idempotency_key": idempotency_key,
                "payload": json.dumps(payload or {}, default=str),
            },
        )
        db.commit()
        return {"id": job_id, "status": "QUEUED"}
    finally:
        db.close()


def job_status_update(
    job_id: str,
    status: str,
    result: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> dict:
    """
    Transition a job to a new status.
    Valid statuses: QUEUED, RUNNING, SUCCESS, FAILED, NEEDS_HUMAN.
    """
    valid = {"QUEUED", "RUNNING", "SUCCESS", "FAILED", "NEEDS_HUMAN"}
    if status not in valid:
        raise ValueError(f"Invalid status '{status}'. Must be one of {valid}")

    updates = ["status = :status", "updated_at = now()"]
    params: dict[str, Any] = {"id": job_id, "status": status}

    if result is not None:
        updates.append("result = CAST(:result AS jsonb)")
        params["result"] = json.dumps(result, default=str)
    if error_message is not None:
        updates.append("error_message = :err")
        params["err"] = error_message

    set_clause = ", ".join(updates)
    db = _session()
    try:
        db.execute(
            text(f"UPDATE jobs SET {set_clause} WHERE id = CAST(:id AS uuid)"),
            params,
        )
        db.commit()

        row = db.execute(
            text("SELECT id, status, updated_at FROM jobs WHERE id = CAST(:id AS uuid)"),
            {"id": job_id},
        ).fetchone()

        return {
            "id": str(row.id),
            "status": row.status,
            "updated_at": row.updated_at.isoformat(),
        } if row else {"error": "job not found"}
    finally:
        db.close()
