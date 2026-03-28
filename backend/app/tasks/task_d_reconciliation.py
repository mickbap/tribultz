"""Task D - Reconciliation: compare CSV receivables against invoices."""

from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.celery_app import celery
from app.tools.postgres_tool import insert_audit_log, job_status_update
from app.tools.s3_tool import put_object

logger = logging.getLogger(__name__)

DEFAULT_TOLERANCE = Decimal("0.01")

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


def _ensure_table() -> None:
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
    transaction_id: str | None = None,
) -> dict:
    """
    Reconcile CSV receivables against known invoices.
    """
    task_id = str(self.request.id) if self.request and self.request.id else ""
    if task_id:
        job_status_update(job_id=task_id, status="RUNNING", transaction_id=transaction_id)

    try:
        import base64

        _ensure_table()
        tol = Decimal(tolerance or str(DEFAULT_TOLERANCE))
        now_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        csv_bytes = base64.b64decode(csv_receivables_b64)
        text_io = io.StringIO(csv_bytes.decode("utf-8"))
        reader = csv.DictReader(text_io, delimiter=";")
        receivables: dict[str, dict[str, Decimal | str]] = {}
        for row in reader:
            invoice_number = row.get("invoice_number", "").strip()
            if invoice_number:
                receivables[invoice_number] = {
                    "expected_amount": Decimal(row.get("expected_amount", "0") or "0"),
                    "received_amount": Decimal(row.get("received_amount", "0") or "0"),
                    "received_date": row.get("received_date", ""),
                }

        invoice_map = {
            str(invoice["invoice_number"]): Decimal(str(invoice.get("total_amount", "0")))
            for invoice in invoices
        }

        all_keys = set(receivables) | set(invoice_map)
        matched = 0
        exceptions: list[dict[str, str]] = []

        for invoice_number in sorted(all_keys):
            has_receivable = invoice_number in receivables
            has_invoice = invoice_number in invoice_map

            if has_invoice and not has_receivable:
                exceptions.append(
                    {
                        "invoice_number": invoice_number,
                        "type": "MISSING_RECEIVABLE",
                        "message": f"Invoice {invoice_number} has no matching receivable",
                        "invoice_amount": str(invoice_map[invoice_number]),
                    }
                )
                continue

            if has_receivable and not has_invoice:
                exceptions.append(
                    {
                        "invoice_number": invoice_number,
                        "type": "MISSING_INVOICE",
                        "message": f"Receivable {invoice_number} has no matching invoice",
                        "received_amount": str(receivables[invoice_number]["received_amount"]),
                    }
                )
                continue

            receivable = receivables[invoice_number]
            invoice_amount = invoice_map[invoice_number]
            received_amount = Decimal(str(receivable["received_amount"]))
            diff = received_amount - invoice_amount

            if abs(diff) <= tol:
                matched += 1
            elif diff < 0:
                exceptions.append(
                    {
                        "invoice_number": invoice_number,
                        "type": "UNDERPAYMENT",
                        "message": (
                            f"Received {received_amount} < Invoice {invoice_amount} (diff: {diff})"
                        ),
                        "invoice_amount": str(invoice_amount),
                        "received_amount": str(received_amount),
                        "diff": str(diff),
                    }
                )
            else:
                exceptions.append(
                    {
                        "invoice_number": invoice_number,
                        "type": "OVERPAYMENT",
                        "message": (
                            f"Received {received_amount} > Invoice {invoice_amount} (diff: +{diff})"
                        ),
                        "invoice_amount": str(invoice_amount),
                        "received_amount": str(received_amount),
                        "diff": str(diff),
                    }
                )

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
                sa_text(
                    """
                    INSERT INTO reconciliation_runs
                        (id, tenant_id, total_records, matched, exceptions, details)
                    VALUES (
                        CAST(:id AS uuid),
                        CAST(:tenant_id AS uuid),
                        :total_records,
                        :matched,
                        :exceptions_count,
                        CAST(:details AS jsonb)
                    )
                    """
                ),
                {
                    "id": run_id,
                    "tenant_id": tenant_id,
                    "total_records": len(all_keys),
                    "matched": matched,
                    "exceptions_count": len(exceptions),
                    "details": json.dumps(details, default=str),
                },
            )
            db.commit()
        finally:
            db.close()

        report_json = json.dumps({"run_id": run_id, **details}, indent=2, default=str).encode()
        s3_key = f"reconciliation/{tenant_slug}/{now_str}_exceptions.json"
        upload = put_object(key=s3_key, data=report_json, content_type="application/json")

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

        if task_id:
            job_status_update(
                job_id=task_id,
                status="SUCCESS",
                result=result,
                transaction_id=transaction_id,
            )

        logger.info(
            "Task D [%s] run=%s matched=%d exceptions=%d",
            tenant_slug,
            run_id,
            matched,
            len(exceptions),
        )
        return result
    except Exception as exc:
        if task_id:
            job_status_update(
                job_id=task_id,
                status="FAILED",
                error_message=str(exc),
                transaction_id=transaction_id,
            )
        raise
