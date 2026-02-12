"""Audit & Evidence Agent – ensures every execution produces auditable artifacts."""

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])


# ── Schemas ───────────────────────────────────────────────────
class AuditEntry(BaseModel):
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_slug: str = "default"
    user_id: Optional[str] = None


class AuditRecord(BaseModel):
    id: str
    tenant_id: str
    action: str
    entity_type: str
    entity_id: Optional[str]
    checksum: str
    created_at: str


class AuditSearchParams(BaseModel):
    tenant_slug: str = "default"
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    limit: int = Field(default=50, le=200)


# ── Helpers ───────────────────────────────────────────────────
def _compute_checksum(payload: dict) -> str:
    """SHA-256 checksum of the serialised payload for tamper-evidence."""
    raw = str(sorted(payload.items())).encode("utf-8")
    return sha256(raw).hexdigest()


# ── Endpoints ─────────────────────────────────────────────────
@router.post("/log", response_model=AuditRecord)
def create_audit_log(entry: AuditEntry, db: Session = Depends(get_db)):
    """
    Record an auditable event.
    Generates a checksum from the payload so that downstream
    consumers can verify the record was not tampered with.
    """
    checksum = _compute_checksum(entry.payload)
    audit_id = str(uuid4())

    tenant_row = db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug"),
        {"slug": entry.tenant_slug},
    ).fetchone()

    if not tenant_row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Tenant '{entry.tenant_slug}' not found")

    tenant_id = str(tenant_row.id)

    db.execute(
        text("""
            INSERT INTO audit_log (id, tenant_id, user_id, action,
                                   entity_type, entity_id, payload)
            VALUES (CAST(:id AS uuid), CAST(:tenant_id AS uuid), CAST(:user_id AS uuid), :action,
                    :entity_type, :entity_id, CAST(:payload AS jsonb))
        """),
        {
            "id": audit_id,
            "tenant_id": tenant_id,
            "user_id": entry.user_id,
            "action": entry.action,
            "entity_type": entry.entity_type,
            "entity_id": entry.entity_id,
            "payload": __import__("json").dumps({**entry.payload, "_checksum": checksum}),
        },
    )
    db.commit()

    return AuditRecord(
        id=audit_id,
        tenant_id=tenant_id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        checksum=checksum,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/search", response_model=list[AuditRecord])
def search_audit_log(params: AuditSearchParams, db: Session = Depends(get_db)):
    """Search audit log entries with optional filters."""
    filters = ["t.slug = :slug"]
    bind: dict[str, Any] = {"slug": params.tenant_slug, "limit": params.limit}

    if params.entity_type:
        filters.append("al.entity_type = :entity_type")
        bind["entity_type"] = params.entity_type
    if params.entity_id:
        filters.append("al.entity_id = :entity_id")
        bind["entity_id"] = params.entity_id

    where = " AND ".join(filters)
    rows = db.execute(
        text(f"""
            SELECT al.id, al.tenant_id, al.action, al.entity_type,
                   al.entity_id, al.payload, al.created_at
            FROM audit_log al
            JOIN tenants t ON t.id = al.tenant_id
            WHERE {where}
            ORDER BY al.created_at DESC
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    results = []
    for r in rows:
        payload = r.payload if isinstance(r.payload, dict) else {}
        results.append(AuditRecord(
            id=str(r.id),
            tenant_id=str(r.tenant_id),
            action=r.action,
            entity_type=r.entity_type,
            entity_id=str(r.entity_id) if r.entity_id else None,
            checksum=payload.get("_checksum", ""),
            created_at=r.created_at.isoformat() if r.created_at else "",
        ))
    return results
