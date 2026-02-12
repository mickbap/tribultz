"""Validation router – tax-calculation & rule-validation endpoints."""

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(prefix="/api/v1/validation", tags=["validation"])


# ── Enums ─────────────────────────────────────────────────────
class TaxType(str, Enum):
    CBS = "CBS"
    IBS = "IBS"
    IS = "IS"


# ── Request / Response schemas ────────────────────────────────
class TaxCalculationRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1, max_length=100)
    ncm_code: Optional[str] = Field(None, max_length=10)
    tax_type: TaxType
    base_amount: Decimal = Field(..., gt=0, decimal_places=2)
    reference_date: date = Field(default_factory=date.today)

    @field_validator("base_amount", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v))


class TaxCalculationResponse(BaseModel):
    tax_type: str
    rule_code: str
    rate: Decimal
    base_amount: Decimal
    tax_amount: Decimal
    reference_date: date


class ValidateCNPJRequest(BaseModel):
    cnpj: str = Field(..., min_length=14, max_length=18)


class ValidateCNPJResponse(BaseModel):
    cnpj: str
    is_valid: bool
    formatted: str


class RuleLookupResponse(BaseModel):
    rule_code: str
    description: Optional[str]
    tax_type: str
    rate: Decimal
    valid_from: date
    valid_to: Optional[date]


# ── Helpers ───────────────────────────────────────────────────
def _strip_cnpj(raw: str) -> str:
    return "".join(c for c in raw if c.isdigit())


def _validate_cnpj_digits(digits: str) -> bool:
    """Validates CNPJ check-digits (Brazilian algorithm)."""
    if len(digits) != 14 or digits == digits[0] * 14:
        return False

    def _calc(d, weights):
        s = sum(int(d[i]) * w for i, w in enumerate(weights))
        r = s % 11
        return 0 if r < 2 else 11 - r

    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    if _calc(digits, w1) != int(digits[12]):
        return False
    if _calc(digits, w2) != int(digits[13]):
        return False
    return True


def _format_cnpj(digits: str) -> str:
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


# ── Endpoints ─────────────────────────────────────────────────
@router.post("/calculate-tax", response_model=TaxCalculationResponse)
def calculate_tax(req: TaxCalculationRequest, db: Session = Depends(get_db)):
    """Look up the applicable tax rule and compute the tax amount."""
    row = db.execute(
        text("""
            SELECT tr.rule_code, tr.rate
            FROM tax_rules tr
            JOIN tenants t ON t.id = tr.tenant_id
            WHERE t.slug = :slug
              AND tr.tax_type = :tax_type
              AND tr.valid_from <= :ref_date
              AND (tr.valid_to IS NULL OR tr.valid_to >= :ref_date)
            ORDER BY tr.valid_from DESC
            LIMIT 1
        """),
        {
            "slug": req.tenant_slug,
            "tax_type": req.tax_type.value,
            "ref_date": req.reference_date,
        },
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No {req.tax_type.value} rule found for tenant '{req.tenant_slug}' "
                   f"on {req.reference_date}",
        )

    rate = Decimal(str(row.rate))
    tax_amount = (req.base_amount * rate).quantize(Decimal("0.01"))

    return TaxCalculationResponse(
        tax_type=req.tax_type.value,
        rule_code=row.rule_code,
        rate=rate,
        base_amount=req.base_amount,
        tax_amount=tax_amount,
        reference_date=req.reference_date,
    )


@router.post("/validate-cnpj", response_model=ValidateCNPJResponse)
def validate_cnpj(req: ValidateCNPJRequest):
    """Validate a Brazilian CNPJ number."""
    digits = _strip_cnpj(req.cnpj)
    is_valid = _validate_cnpj_digits(digits)
    return ValidateCNPJResponse(
        cnpj=digits,
        is_valid=is_valid,
        formatted=_format_cnpj(digits) if is_valid else digits,
    )


@router.get("/rules/{tenant_slug}", response_model=list[RuleLookupResponse])
def list_rules(
    tenant_slug: str,
    tax_type: Optional[TaxType] = None,
    ref_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Return all active tax rules for a tenant, optionally filtered."""
    ref = ref_date or date.today()
    params: dict = {"slug": tenant_slug, "ref_date": ref}

    type_filter = ""
    if tax_type:
        type_filter = "AND tr.tax_type = :tax_type"
        params["tax_type"] = tax_type.value

    rows = db.execute(
        text(f"""
            SELECT tr.rule_code, tr.description, tr.tax_type,
                   tr.rate, tr.valid_from, tr.valid_to
            FROM tax_rules tr
            JOIN tenants t ON t.id = tr.tenant_id
            WHERE t.slug = :slug
              AND tr.valid_from <= :ref_date
              AND (tr.valid_to IS NULL OR tr.valid_to >= :ref_date)
              {type_filter}
            ORDER BY tr.tax_type, tr.valid_from DESC
        """),
        params,
    ).fetchall()

    return [
        RuleLookupResponse(
            rule_code=r.rule_code,
            description=r.description,
            tax_type=r.tax_type,
            rate=r.rate,
            valid_from=r.valid_from,
            valid_to=r.valid_to,
        )
        for r in rows
    ]
