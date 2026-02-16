"""CBS / IBS validation router – TaxEngine-powered invoice check."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.auth import User

router = APIRouter(tags=["validate"])

TWO_PLACES = Decimal("0.01")


# ── Schemas ───────────────────────────────────────────────────
class InvoiceItem(BaseModel):
    sku: str
    description: str
    base_amount: Decimal = Field(..., gt=0)
    cbs_rule_code: str = "STD_CBS"
    ibs_rule_code: str = "STD_IBS"


class ValidateRequest(BaseModel):
    company_id: str
    invoice_number: str
    issue_date: date
    declared_cbs: Decimal
    declared_ibs: Decimal
    items: list[InvoiceItem]


class ItemResult(BaseModel):
    sku: str
    description: str
    base_amount: Decimal
    cbs_rate: Decimal
    cbs_amount: Decimal
    ibs_rate: Decimal
    ibs_amount: Decimal


class ValidateResponse(BaseModel):
    status: str                  # PASS | FAIL
    invoice_number: str
    issue_date: date
    declared_cbs: Decimal
    declared_ibs: Decimal
    calculated_cbs: Decimal
    calculated_ibs: Decimal
    cbs_match: bool
    ibs_match: bool
    items: list[ItemResult]
    message: str


# ── Tax engine helper ─────────────────────────────────────────
def _lookup_rate(
    db: Session,
    tenant_id: str,
    rule_code: str,
    tax_type: str,
    ref_date: date,
) -> Decimal:
    """Fetch the rate for a given rule_code + tax_type from the DB."""
    row = db.execute(
        text("""
            SELECT tr.rate
            FROM tax_rules tr
            WHERE tr.tenant_id = CAST(:tenant_id AS uuid)
              AND tr.rule_code  = :rule_code
              AND tr.tax_type   = :tax_type
              AND tr.valid_from <= :ref_date
              AND (tr.valid_to IS NULL OR tr.valid_to >= :ref_date)
            ORDER BY tr.valid_from DESC
            LIMIT 1
        """),
        {
            "tenant_id": tenant_id,
            "rule_code": rule_code,
            "tax_type": tax_type,
            "ref_date": ref_date,
        },
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Rule '{rule_code}' ({tax_type}) not found for tenant "
                   f"'{tenant_id}' on {ref_date}",
        )
    return Decimal(str(row.rate))


# ── Endpoint ──────────────────────────────────────────────────
@router.post("/validate/cbs-ibs", response_model=ValidateResponse)
def validate_cbs_ibs(
    req: ValidateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Validate an invoice's declared CBS & IBS against the TaxEngine rules
    stored in Postgres.  Returns PASS when both match, FAIL otherwise.
    """
    total_cbs = Decimal("0")
    total_ibs = Decimal("0")
    item_results: list[ItemResult] = []

    tenant_id = str(current_user.tenant_id)

    for item in req.items:
        cbs_rate = _lookup_rate(
            db, tenant_id, item.cbs_rule_code, "CBS", req.issue_date,
        )
        ibs_rate = _lookup_rate(
            db, tenant_id, item.ibs_rule_code, "IBS", req.issue_date,
        )

        cbs_amount = (item.base_amount * cbs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
        ibs_amount = (item.base_amount * ibs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)

        total_cbs += cbs_amount
        total_ibs += ibs_amount

        item_results.append(
            ItemResult(
                sku=item.sku,
                description=item.description,
                base_amount=item.base_amount,
                cbs_rate=cbs_rate,
                cbs_amount=cbs_amount,
                ibs_rate=ibs_rate,
                ibs_amount=ibs_amount,
            )
        )

    total_cbs = total_cbs.quantize(TWO_PLACES, ROUND_HALF_UP)
    total_ibs = total_ibs.quantize(TWO_PLACES, ROUND_HALF_UP)

    cbs_match = total_cbs == req.declared_cbs.quantize(TWO_PLACES, ROUND_HALF_UP)
    ibs_match = total_ibs == req.declared_ibs.quantize(TWO_PLACES, ROUND_HALF_UP)
    passed = cbs_match and ibs_match

    message = "PASS – Declared values match calculated taxes." if passed else (
        f"FAIL – Mismatch detected. "
        f"CBS: declared={req.declared_cbs} vs calculated={total_cbs}. "
        f"IBS: declared={req.declared_ibs} vs calculated={total_ibs}."
    )

    return ValidateResponse(
        status="PASS" if passed else "FAIL",
        invoice_number=req.invoice_number,
        issue_date=req.issue_date,
        declared_cbs=req.declared_cbs,
        declared_ibs=req.declared_ibs,
        calculated_cbs=total_cbs,
        calculated_ibs=total_ibs,
        cbs_match=cbs_match,
        ibs_match=ibs_match,
        items=item_results,
        message=message,
    )
