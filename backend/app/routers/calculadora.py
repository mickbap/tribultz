"""Calculadora CBS/IBS — tax calculator endpoints.

Public endpoint is rate-limited (same as diagnostic funnel).
Authenticated endpoint has no rate limit and can use tenant-specific rates.

Data governance: No data is stored. Calculations are stateless and in-memory.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from app.data.cst_regimes import CST_REGIMES
from app.data.uf_rates import VALID_UF_CODES
from app.services.rate_limit import RateLimiter
from app.services.tax_rate_resolver import NcmNaoDeterminavel, calculate_full

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calculadora"])

# ── Rate limiting (public endpoints only) ────────────────────────────────────

_rate_limiter = RateLimiter()

_daily_limiter = RateLimiter()
_daily_limiter.limit = 20
_daily_limiter.ttl = 86400


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Schemas ──────────────────────────────────────────────────────────────────

class CalculadoraRequest(BaseModel):
    ncm_code: str | None = None
    c_class_trib: str | None = None
    uf_destino: str
    municipio: str | None = None
    base_value: Decimal
    quantity: Decimal = Decimal("1")
    cst: str = "000"
    # "teste_2026" (default): alíquotas reduzidas de emissão de 2026 (CBS 0,9% / IBS 0,1%)
    # — o que vai na NF-e agora. "regime_cheio": carga plena (8,8 / 17,7) p/ projeção.
    periodo: str = "teste_2026"

    @field_validator("periodo")
    @classmethod
    def validate_periodo(cls, v: str) -> str:
        v = v.strip()
        if v not in ("teste_2026", "regime_cheio"):
            raise ValueError("periodo deve ser 'teste_2026' ou 'regime_cheio'")
        return v

    @field_validator("uf_destino")
    @classmethod
    def validate_uf(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in VALID_UF_CODES:
            raise ValueError(f"UF inválido: {v}")
        return v

    @field_validator("base_value")
    @classmethod
    def validate_base_value(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("base_value deve ser maior que zero")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity deve ser maior que zero")
        return v

    @field_validator("ncm_code")
    @classmethod
    def validate_ncm(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not re.match(r"^\d{8}$", v):
            raise ValueError("NCM deve ter exatamente 8 dígitos")
        return v

    @field_validator("c_class_trib")
    @classmethod
    def validate_classtrib(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not re.match(r"^\d{6}$", v):
            raise ValueError("cClassTrib deve ter exatamente 6 dígitos")
        return v

    @field_validator("cst")
    @classmethod
    def validate_cst(cls, v: str) -> str:
        v = v.strip()
        if v not in CST_REGIMES:
            raise ValueError(f"CST inválido: {v}")
        return v


class CalculadoraResponse(BaseModel):
    vBC: Decimal
    pCBS: Decimal
    vCBS: Decimal
    pIBSUF: Decimal
    vIBSUF: Decimal
    pIBSMun: Decimal
    vIBSMun: Decimal
    vIBS: Decimal
    total_tributos: Decimal
    aliquota_efetiva: Decimal
    rate_source: str
    cst: str
    cst_desc: str
    periodo: str
    xml_snippet: str
    data_policy: str
    upgrade_cta: str


DATA_POLICY = (
    "Nenhum dado é armazenado. O cálculo é processado em memória e "
    "descartado imediatamente. Consulte /api/v1/public/data-policy."
)

UPGRADE_CTA = (
    "Crie sua conta gratuita para salvar cálculos, gerar relatórios PDF "
    "e validar XMLs completos com 20 regras de conformidade."
)


# ── Public endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/api/v1/public/calculadora/regime-geral",
    response_model=CalculadoraResponse,
)
async def public_calculadora(request: Request, body: CalculadoraRequest):
    """Public CBS/IBS tax calculator — no login required, rate-limited.

    Calculate CBS and IBS taxes for a given operation. Returns the full
    breakdown with effective rates and a ready-to-use XML snippet.

    Rate limits: 10 req/min + 20 req/day per IP.
    """
    ip = _client_ip(request)
    _rate_limiter.check_or_raise(f"calc:{ip}")
    _daily_limiter.check_or_raise(f"calc_daily:{ip}")

    # #685: sem lastro unânime na fonte não há valor a devolver. Devolver um
    # número derivado do capítulo NCM era o defeito; devolver 1.0 por padrão
    # seria o mesmo erro com outra cara.
    try:
        result = calculate_full(
            vBC=body.base_value,
            quantity=body.quantity,
            ncm=body.ncm_code,
            uf=body.uf_destino,
            cst=body.cst,
            periodo=body.periodo,
        )
    except NcmNaoDeterminavel as _e:
        raise HTTPException(
            status_code=422,
            detail={
                "erro": "nao_determinavel",
                "ncm": _e.ncm,
                "unanime": False,
                "fontes_cClassTrib_usadas": _e.fontes,
                "motivo": _e.motivo,
            },
        )

    return CalculadoraResponse(
        vBC=result.vBC,
        pCBS=result.pCBS, vCBS=result.vCBS,
        pIBSUF=result.pIBSUF, vIBSUF=result.vIBSUF,
        pIBSMun=result.pIBSMun, vIBSMun=result.vIBSMun,
        vIBS=result.vIBS,
        total_tributos=result.total_tributos,
        aliquota_efetiva=result.aliquota_efetiva,
        rate_source=result.rate_source,
        cst=result.cst,
        cst_desc=result.cst_desc,
        periodo=body.periodo,
        xml_snippet=result.xml_snippet,
        data_policy=DATA_POLICY,
        upgrade_cta=UPGRADE_CTA,
    )


# ── UF rates lookup (public) ────────────────────────────────────────────────

@router.get("/api/v1/public/calculadora/uf-rates")
async def public_uf_rates():
    """Return reference CBS/IBS rates for all 27 Brazilian states."""
    from app.data.uf_rates import UF_RATES
    return {
        uf: {
            "uf_name": data["uf_name"],
            "cbs_rate": str(data["cbs_rate"]),
            "ibs_uf_rate": str(data["ibs_uf_rate"]),
            "ibs_mun_rate": str(data["ibs_mun_rate"]),
            "ibs_total": str(data["ibs_uf_rate"] + data["ibs_mun_rate"]),
        }
        for uf, data in sorted(UF_RATES.items())
    }


# ── CST list (public) ───────────────────────────────────────────────────────

@router.get("/api/v1/public/calculadora/cst-list")
async def public_cst_list():
    """Return all valid CST codes with descriptions."""
    return [
        {"code": code, "desc": data["desc"], "regime": data["regime"]}
        for code, data in sorted(CST_REGIMES.items())
    ]
