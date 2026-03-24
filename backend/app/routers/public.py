"""Public endpoints — no authentication required.

Rate-limited to prevent abuse. Used for the freemium diagnostic funnel.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.routers.validate_xml import validate_xml, ValidationResult
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

# Stricter rate limit for public endpoints: 10 req/min per IP
_rate_limiter = RateLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Schemas ──────────────────────────────────────────────────────────────────

class PublicFindingSummary(BaseModel):
    rule_id: str
    severity: str
    title: str


class PublicValidationResult(BaseModel):
    """Simplified validation result for the freemium tier.

    Shows rule names and severity but redacts detailed evidence,
    xpath, snippets and recommendations (available in paid plans).
    """
    document_type: str
    status: str  # PASS | FAIL
    total_findings: int
    fatals: int
    alerts: int
    findings: list[PublicFindingSummary]
    rules_checked: int
    upgrade_cta: str


# Total rules the engine checks (for the "X rules checked" display)
RULES_CHECKED = 14


def _to_public_result(result: ValidationResult) -> PublicValidationResult:
    """Convert full ValidationResult to freemium-safe output."""
    status = "PASS" if result.fatals == 0 else "FAIL"
    findings = [
        PublicFindingSummary(
            rule_id=f.rule_id,
            severity=f.severity,
            title=f.title,
        )
        for f in result.findings
    ]
    return PublicValidationResult(
        document_type=result.document_type,
        status=status,
        total_findings=len(result.findings),
        fatals=result.fatals,
        alerts=result.alerts,
        findings=findings,
        rules_checked=RULES_CHECKED,
        upgrade_cta="Crie sua conta gratuita para ver o relatório completo com evidências, recomendações e exportação PDF.",
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/validate", response_model=PublicValidationResult)
async def public_validate(
    request: Request,
    file: UploadFile = File(None),
    xml_content: str = Form(None),
):
    """Public XML validation — no login required, rate-limited.

    Upload an NF-e/NFC-e/NFS-e XML and get an instant conformity diagnostic.
    Returns rule hits with severity but redacts detailed evidence (paid feature).
    """
    ip = _client_ip(request)
    _rate_limiter.check_or_raise(f"public:{ip}")

    if file:
        raw = await file.read()
        if len(raw) > 2 * 1024 * 1024:  # 2MB limit
            raise HTTPException(status_code=413, detail="Arquivo XML excede 2MB.")
        xml = raw.decode("utf-8")
    elif xml_content:
        if len(xml_content) > 2 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="XML excede 2MB.")
        xml = xml_content
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo XML ou xml_content.")

    if not xml.strip():
        raise HTTPException(status_code=400, detail="XML vazio.")

    result = validate_xml(xml)
    return _to_public_result(result)


@router.get("/health")
def public_health():
    """Public health check — useful for uptime monitoring."""
    return {"status": "ok", "service": "tribultz-public"}
