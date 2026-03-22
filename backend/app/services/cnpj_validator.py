"""CNPJ validation via BrasilAPI (free, no API key required).

Primary: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
Fallback: https://receitaws.com.br/v1/cnpj/{cnpj} (3 req/min free)

Graceful degradation: if both APIs are unavailable, allow registration
with a warning log (never block user registration due to external API).
"""

import logging
import re
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
RECEITAWS_URL = "https://receitaws.com.br/v1/cnpj/{cnpj}"
TIMEOUT_SECONDS = 5.0


@dataclass
class CnpjResult:
    valid: bool
    cnpj: str
    company_name: str
    status: str  # "ATIVA", "BAIXADA", etc.
    error: str


def _digits_only(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


async def validate_cnpj(cnpj: str) -> CnpjResult:
    """Validate CNPJ against external APIs. Returns result with valid flag."""
    digits = _digits_only(cnpj)
    if len(digits) != 14:
        return CnpjResult(
            valid=False, cnpj=digits, company_name="", status="",
            error="CNPJ deve ter 14 digitos.",
        )

    # Try BrasilAPI first
    result = await _try_brasilapi(digits)
    if result is not None:
        return result

    # Fallback to ReceitaWS
    result = await _try_receitaws(digits)
    if result is not None:
        return result

    # Both APIs failed — allow registration with warning
    logger.warning("cnpj_validation_unavailable", extra={"cnpj": digits})
    return CnpjResult(
        valid=True, cnpj=digits, company_name="", status="API_UNAVAILABLE",
        error="",
    )


async def _try_brasilapi(digits: str) -> CnpjResult | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(BRASILAPI_URL.format(cnpj=digits))
            if resp.status_code == 404:
                return CnpjResult(
                    valid=False, cnpj=digits, company_name="", status="NOT_FOUND",
                    error="CNPJ nao encontrado na base da Receita Federal.",
                )
            if resp.status_code != 200:
                return None  # Try fallback
            data = resp.json()
            situacao = str(data.get("descricao_situacao_cadastral", "")).upper()
            company_name = str(data.get("razao_social", ""))
            if situacao != "ATIVA":
                return CnpjResult(
                    valid=False, cnpj=digits, company_name=company_name,
                    status=situacao,
                    error=f"CNPJ com situacao cadastral: {situacao}. Apenas CNPJs ativos sao aceitos.",
                )
            return CnpjResult(
                valid=True, cnpj=digits, company_name=company_name,
                status="ATIVA", error="",
            )
    except Exception as exc:
        logger.warning("brasilapi_error", extra={"error": str(exc)})
        return None


async def _try_receitaws(digits: str) -> CnpjResult | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(RECEITAWS_URL.format(cnpj=digits))
            if resp.status_code == 404:
                return CnpjResult(
                    valid=False, cnpj=digits, company_name="", status="NOT_FOUND",
                    error="CNPJ nao encontrado na base da Receita Federal.",
                )
            if resp.status_code == 429:
                return None  # Rate limited, fail to fallback
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") == "ERROR":
                return CnpjResult(
                    valid=False, cnpj=digits, company_name="", status="ERROR",
                    error=str(data.get("message", "CNPJ invalido.")),
                )
            situacao = str(data.get("situacao", "")).upper()
            company_name = str(data.get("nome", ""))
            if situacao != "ATIVA":
                return CnpjResult(
                    valid=False, cnpj=digits, company_name=company_name,
                    status=situacao,
                    error=f"CNPJ com situacao: {situacao}. Apenas CNPJs ativos sao aceitos.",
                )
            return CnpjResult(
                valid=True, cnpj=digits, company_name=company_name,
                status="ATIVA", error="",
            )
    except Exception as exc:
        logger.warning("receitaws_error", extra={"error": str(exc)})
        return None
