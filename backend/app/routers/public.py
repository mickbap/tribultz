"""Public endpoints — no authentication required.

Rate-limited to prevent abuse. Used for the freemium diagnostic funnel.

Data governance: XML content submitted to this endpoint is processed in-memory
only, never persisted to disk or database. No PII extraction or storage occurs.
See GET /api/v1/public/data-policy for the full commitment.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel

from app.data.cest_ncm import (
    CEST_DATA_SOURCE,
    CEST_DATA_VERSION,
    lookup_ncm_st,
)
from app.routers.validate_xml import validate_xml, ValidationResult
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

# ── Rate limiting ────────────────────────────────────────────────────────────
# Per-minute: burst protection (10 req/min)
_rate_limiter = RateLimiter()

# Per-day: freemium cap (20 validations/day per IP)
_daily_limiter = RateLimiter()
_daily_limiter.limit = 20
_daily_limiter.ttl = 86400  # 24 hours

# Freemium guardrail: max findings shown without login
MAX_FREE_FINDINGS = 3


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

    Shows up to 3 findings with rule names and severity.
    Redacts detailed evidence, xpath, snippets and recommendations.
    Full results available in paid plans.
    """

    document_type: str
    status: str  # PASS | FAIL
    total_findings: int
    findings_shown: int
    findings_hidden: int
    fatals: int
    alerts: int
    findings: list[PublicFindingSummary]
    rules_checked: int
    upgrade_cta: str
    data_policy: str


# Total rules the engine checks (14 base + 4 cross-validation S13)
RULES_CHECKED = 18

DATA_POLICY_SUMMARY = (
    "Seu XML é processado em memória e descartado imediatamente após a validação. "
    "Nenhum dado fiscal, CNPJ ou informação pessoal é armazenado, "
    "compartilhado ou utilizado para qualquer outra finalidade. "
    "Consulte /api/v1/public/data-policy para detalhes completos."
)


def _to_public_result(result: ValidationResult) -> PublicValidationResult:
    """Convert full ValidationResult to freemium-safe output."""
    status = "PASS" if result.fatals == 0 else "FAIL"
    all_findings = [
        PublicFindingSummary(
            rule_id=f.rule_id,
            severity=f.severity,
            title=f.title,
        )
        for f in result.findings
    ]
    # Guardrail: show only first N findings, blur the rest
    shown = all_findings[:MAX_FREE_FINDINGS]
    hidden = len(all_findings) - len(shown)

    cta = (
        "Crie sua conta gratuita para ver o relatório completo com "
        "evidências, recomendações e exportação PDF."
    )
    if hidden > 0:
        cta = (
            f"Mais {hidden} {'problema encontrado' if hidden == 1 else 'problemas encontrados'} — "
            "crie sua conta para ver todos os detalhes, evidências e recomendações de correção."
        )

    return PublicValidationResult(
        document_type=result.document_type,
        status=status,
        total_findings=len(all_findings),
        findings_shown=len(shown),
        findings_hidden=hidden,
        fatals=result.fatals,
        alerts=result.alerts,
        findings=shown,
        rules_checked=RULES_CHECKED,
        upgrade_cta=cta,
        data_policy=DATA_POLICY_SUMMARY,
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
    Returns up to 3 findings with severity. Detailed evidence requires a paid plan.

    Rate limits: 10 req/min + 20 req/day per IP.

    Data commitment: XML is processed in-memory only and immediately discarded.
    No fiscal data, CNPJ, or PII is stored or shared.
    """
    ip = _client_ip(request)
    _rate_limiter.check_or_raise(f"public:{ip}")
    _daily_limiter.check_or_raise(f"public_daily:{ip}")

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


@router.get("/data-policy")
def public_data_policy():
    """Data governance policy for the public validation endpoint.

    Transparent commitment to how submitted XML data is handled.
    """
    return {
        "service": "Tribultz — Diagnóstico Gratuito de Conformidade Fiscal",
        "version": "1.0",
        "effective_date": "2026-03-24",
        "commitments": [
            {
                "id": "NO_STORAGE",
                "title": "Sem armazenamento",
                "description": (
                    "O XML enviado ao endpoint /api/v1/public/validate é processado "
                    "exclusivamente em memória (RAM) durante a validação. Nenhum conteúdo "
                    "do XML é gravado em disco, banco de dados, object storage (S3) ou "
                    "qualquer outro meio persistente."
                ),
            },
            {
                "id": "NO_PII_EXTRACTION",
                "title": "Sem extração de dados pessoais",
                "description": (
                    "O motor de validação analisa apenas a estrutura fiscal do XML "
                    "(CST, cClassTrib, CEST, alíquotas IBS/CBS). Campos como CNPJ, "
                    "razão social, endereço ou dados de produtos NÃO são extraídos, "
                    "indexados ou armazenados."
                ),
            },
            {
                "id": "NO_SHARING",
                "title": "Sem compartilhamento",
                "description": (
                    "Os dados do XML não são compartilhados com terceiros, "
                    "parceiros comerciais, serviços de analytics ou modelos de IA. "
                    "O processamento ocorre inteiramente nos servidores Tribultz."
                ),
            },
            {
                "id": "NO_LOGGING_CONTENT",
                "title": "Sem log do conteúdo fiscal",
                "description": (
                    "Os logs do sistema registram apenas metadados operacionais "
                    "(IP de origem, timestamp, tipo de documento, contagem de findings). "
                    "O conteúdo do XML NUNCA é incluído em logs."
                ),
            },
            {
                "id": "IMMEDIATE_DISCARD",
                "title": "Descarte imediato",
                "description": (
                    "Após a resposta HTTP ser enviada, a referência ao XML em memória "
                    "é liberada e sujeita à coleta de lixo do runtime Python. "
                    "Não há cache, fila ou reprocessamento posterior."
                ),
            },
            {
                "id": "LGPD_COMPLIANCE",
                "title": "Conformidade LGPD",
                "description": (
                    "Este endpoint opera em conformidade com a Lei Geral de Proteção "
                    "de Dados (Lei 13.709/2018). Como nenhum dado pessoal é armazenado, "
                    "não há necessidade de base legal para tratamento. O titular pode "
                    "exercer seus direitos via dpo@tribultz.com.br."
                ),
            },
        ],
        "contact": {
            "dpo_email": "dpo@tribultz.com.br",
            "privacy_page": "/privacy",
        },
    }


@router.get("/health")
def public_health():
    """Public health check — useful for uptime monitoring."""
    return {"status": "ok", "service": "tribultz-public"}


# ── CEST × NCM lookup (#275 fase 2) ──────────────────────────────────────────

class CestNcmLookupResponse(BaseModel):
    ncm: str
    is_st: bool
    matched_prefix: str | None
    segments: list[str]
    source: str
    data_version: str


@router.get(
    "/cest/_meta",
    summary="Metadados da base CEST (versão, fonte, prefixos cobertos)",
)
def get_cest_meta() -> dict:
    # NOTE: este endpoint deve vir ANTES de /cest/{ncm} para não ser capturado
    # pela rota dinâmica.
    from app.data.cest_ncm import ST_NCM_PREFIXES
    return {
        "source": CEST_DATA_SOURCE,
        "data_version": CEST_DATA_VERSION,
        "segments_count": len(ST_NCM_PREFIXES),
        "prefixes_count": sum(len(v) for v in ST_NCM_PREFIXES.values()),
        "segments": list(ST_NCM_PREFIXES.keys()),
    }


@router.get(
    "/cest/{ncm}",
    response_model=CestNcmLookupResponse,
    summary="Verifica se NCM está sujeito a Substituição Tributária (ST)",
)
def get_cest_for_ncm(ncm: str) -> CestNcmLookupResponse:
    """Lookup NCM → ST (Convênio ICMS 142/2018, subset curado).

    Quando `is_st=True`, o produto **deve** declarar `<CEST>` na NF-e.
    Quando `is_st=False`, o NCM não consta no subset conhecido —
    o cliente deve tratar a ausência de CEST como ALERT informativo,
    não como erro fatal (subset não cobre 100% do Conv. 142).
    """
    return CestNcmLookupResponse(**lookup_ncm_st(ncm))
