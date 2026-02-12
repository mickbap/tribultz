"""Task D – Reconciliation: compare CSV receivables against invoices → exceptions."""

import csv
import io
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.celery_app import celery
from app.tools.postgres_tool import insert_audit_log
from app.tools.s3_tool import put_object

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
DEFAULT_TOLERANCE = Decimal("0.01")


# ── Reconciliation exceptions table ──────────────────────────
_RECON_DDL = """
CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    run_date      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    total_records INT           NOT NULL DEFAULT 0,
    matched       INT           NOT NULL DEFAULT 0,
    exceptions    INT           NOT NULL DEFAULT 0,
    details       JSONB,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_recon_tenant ON reconciliation_runs(tenant_id);
"""


def _ensure_table():
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text(_RECON_DDL))
        db.commit()
    finally:
        db.close()


@celery.task(name="task_d_reconciliation", bind=True, max_retries=3)
def task_d_reconciliation(
    self,
    tenant_id: str,
    tenant_slug: str,
    csv_receivables_b64: str,
    invoices: list[dict],
    tolerance: str = "0.01",
) -> dict:
    """
    Reconcile CSV receivables (from ERP/bank) against known invoices.

    CSV columns: invoice_number;expected_amount;received_amount;received_date
    invoices: [{invoice_number, total_amount}] — from internal data

    1. Parse CSV receivables
    2. Match by invoice_number
    3. Flag exceptions:
        - MISSING_RECEIVABLE (invoice has no receivable)
        - MISSING_INVOICE (receivable has no invoice)
        - AMOUNT_MISMATCH (|expected - received| > tolerance)
        - UNDERPAYMENT / OVERPAYMENT
    4. Persist run + upload exception report to MinIO
    5. Audit-log
    """
    import base64

    _ensure_table()
    tol = Decimal(tolerance)
    now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    # Parse CSV
    csv_bytes = base64.b64decode(csv_receivables_b64)
    text_io = io.StringIO(csv_bytes.decode("utf-8"))
    reader = csv.DictReader(text_io, delimiter=";")
    receivables: dict[str, dict] = {}
    for row in reader:
        inv_num = row.get("invoice_number", "").strip()
        if inv_num:
            receivables[inv_num] = {
                "expected_amount": Decimal(row.get("expected_amount", "0") or "0"),
                "received_amount": Decimal(row.get("received_amount", "0") or "0"),
                "received_date": row.get("received_date", ""),
            }

    # Build invoice lookup
    invoice_map: dict[str, Decimal] = {
        inv["invoice_number"]: Decimal(str(inv.get("total_amount", "0")))
        for inv in invoices
    }

    # Reconcile
    all_keys = set(list(receivables.keys()) + list(invoice_map.keys()))
    matched = 0
    exceptions: list[dict] = []

    for inv_num in sorted(all_keys):
        has_recv = inv_num in receivables
        has_inv = inv_num in invoice_map

        if has_inv and not has_recv:
            exceptions.append({
                "invoice_number": inv_num,
                "type": "MISSING_RECEIVABLE",
                "message": f"Invoice {inv_num} has no matching receivable",
                "invoice_amount": str(invoice_map[inv_num]),
            })
            continue

        if has_recv and not has_inv:
            exceptions.append({
                "invoice_number": inv_num,
                "type": "MISSING_INVOICE",
                "message": f"Receivable {inv_num} has no matching invoice",
                "received_amount": str(receivables[inv_num]["received_amount"]),
            })
            continue

        # Both exist → check amounts
        recv = receivables[inv_num]
        inv_amt = invoice_map[inv_num]
        recv_amt = recv["received_amount"]
        diff = recv_amt - inv_amt

        if abs(diff) <= tol:
            matched += 1
        elif diff < 0:
            exceptions.append({
                "invoice_number": inv_num,
                "type": "UNDERPAYMENT",
                "message": f"Received {recv_amt} < Invoice {inv_amt} (diff: {diff})",
                "invoice_amount": str(inv_amt),
                "received_amount": str(recv_amt),
                "diff": str(diff),
            })
        else:
            exceptions.append({
                "invoice_number": inv_num,
                "type": "OVERPAYMENT",
                "message": f"Received {recv_amt} > Invoice {inv_amt} (diff: +{diff})",
                "invoice_amount": str(inv_amt),
                "received_amount": str(recv_amt),
                "diff": str(diff),
            })

    # Persist run
    from sqlalchemy import text as sa_text
    from app.database import SessionLocal

    run_id = str(uuid4())
    details = {
        "matched": matched,
        "exceptions": exceptions,
        "tolerance": tolerance,
    }

    db = SessionLocal()
    try:
        db.execute(
            sa_text("""
                INSERT INTO reconciliation_runs
                    (id, tenant_id, total_records, matched, exceptions, details)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :total, :matched, :exc_count,
                        CAST(:details AS jsonb))
            """),
            {
                "id": run_id,
                "tid": tenant_id,
                "total": len(all_keys),
                "matched": matched,
                "exc_count": len(exceptions),
                "details": json.dumps(details, default=str),
            },
        )
        db.commit()
    finally:
        db.close()

    # Upload exception report to MinIO
    report_json = json.dumps({"run_id": run_id, **details}, indent=2, default=str).encode()
    s3_key = f"reconciliation/{tenant_slug}/{now_str}_exceptions.json"
    upload = put_object(key=s3_key, data=report_json, content_type="application/json")

    # Audit
    audit = insert_audit_log(
        tenant_id=tenant_id,
        action="reconciliation_completed",
        entity_type="reconciliation_run",
        entity_id=run_id,
        payload={"matched": matched, "exceptions": len(exceptions), "s3_key": s3_key},
    )

    result = {
        "run_id": run_id,
        "total_records": len(all_keys),
        "matched": matched,
        "exceptions_count": len(exceptions),
        "exceptions": exceptions,
        "report_s3_key": s3_key,
        "report_checksum": upload["checksum_sha256"],
        "audit_id": audit["id"],
    }

    logger.info("Task D [%s] run=%s matched=%d exceptions=%d", tenant_slug, run_id, matched, len(exceptions))
    return result
