"""CNPJ validation via BrasilAPI (free, no API key required).

Primary: https://brasilapi.com.br/api/cnpj/v1/{cnpj}
Fallback: https://receitaws.com.br/v1/cnpj/{cnpj} (3 req/min free)

Graceful degradation: if both APIs are unavailable, allow registration
with a warning log (never block user registration due to external API).

LRU cache (TTL 24h, max 500 entries) prevents excessive API calls in batch scenarios.

Formato aceito: 14 caracteres — 12 alfanuméricos (raiz + ordem do
estabelecimento) + 2 dígitos verificadores numéricos. A partir de 31/07/2026
a Receita Federal emite CNPJ alfanumérico (NT Conjunta 2025.001, produção dos
sistemas RFB em 27/07/2026) — CNPJs já existentes continuam 100% numéricos,
formato subset do alfanumérico. Ver docs/context/reference_cnpj_alfanumerico.md.
"""

import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BRASILAPI_URL = settings.CNPJ_PRIMARY_URL
RECEITAWS_URL = settings.CNPJ_FALLBACK_URL
TIMEOUT_SECONDS = 5.0

_CACHE_MAX = 500
_CACHE_TTL = 86400  # 24 hours


@dataclass
class CnpjResult:
    valid: bool
    cnpj: str
    company_name: str
    status: str  # "ATIVA", "BAIXADA", etc.
    error: str


class _CnpjCache:
    """Simple LRU cache with TTL for CNPJ lookups."""

    def __init__(self) -> None:
        self._store: OrderedDict[str, tuple[float, CnpjResult]] = OrderedDict()

    def get(self, cnpj: str) -> CnpjResult | None:
        if cnpj in self._store:
            ts, result = self._store[cnpj]
            if time.monotonic() - ts < _CACHE_TTL:
                self._store.move_to_end(cnpj)
                return result
            del self._store[cnpj]
        return None

    def put(self, cnpj: str, result: CnpjResult) -> None:
        self._store[cnpj] = (time.monotonic(), result)
        self._store.move_to_end(cnpj)
        while len(self._store) > _CACHE_MAX:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


_cnpj_cache = _CnpjCache()


CNPJ_FORMAT_RE = re.compile(r"^[A-Z0-9]{12}\d{2}$")


def normalize_cnpj(cnpj: str) -> str:
    """Remove pontuação (., /, -, espaço) e uppercase — preserva letras.

    CNPJ alfanumérico (RFB, produção 27/07/2026) usa letras nas 12 primeiras
    posições; só os 2 dígitos verificadores finais continuam numéricos.
    """
    return re.sub(r"[.\-/\s]", "", cnpj).upper()


def is_valid_cnpj_format(cnpj: str) -> bool:
    return bool(CNPJ_FORMAT_RE.match(normalize_cnpj(cnpj)))


async def validate_cnpj(cnpj: str) -> CnpjResult:
    """Validate CNPJ against external APIs. Returns result with valid flag.

    Uses LRU cache (24h TTL) to avoid repeated API calls for the same CNPJ.
    """
    normalized = normalize_cnpj(cnpj)
    if not is_valid_cnpj_format(normalized):
        return CnpjResult(
            valid=False, cnpj=normalized, company_name="", status="",
            error="CNPJ deve ter 14 caracteres (12 alfanuméricos + 2 dígitos verificadores).",
        )

    # Check cache first
    cached = _cnpj_cache.get(normalized)
    if cached is not None:
        return cached

    # Try BrasilAPI first
    result = await _try_brasilapi(normalized)
    if result is not None:
        _cnpj_cache.put(normalized, result)
        return result

    # Fallback to ReceitaWS
    result = await _try_receitaws(normalized)
    if result is not None:
        _cnpj_cache.put(normalized, result)
        return result

    # Both APIs failed — allow with warning (don't cache failures)
    logger.warning("cnpj_validation_unavailable", extra={"cnpj": normalized})
    return CnpjResult(
        valid=True, cnpj=normalized, company_name="", status="API_UNAVAILABLE",
        error="",
    )


async def _try_brasilapi(digits: str) -> CnpjResult | None:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(BRASILAPI_URL.format(cnpj=digits))
            if resp.status_code == 404:
                return CnpjResult(
                    valid=False, cnpj=digits, company_name="", status="NOT_FOUND",
                    error="CNPJ não encontrado na base da Receita Federal.",
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
                    error=f"CNPJ com situação cadastral: {situacao}. Apenas CNPJs ativos são aceitos.",
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
                    error="CNPJ não encontrado na base da Receita Federal.",
                )
            if resp.status_code == 429:
                return None  # Rate limited, fail to fallback
            if resp.status_code != 200:
                return None
            data = resp.json()
            if data.get("status") == "ERROR":
                return CnpjResult(
                    valid=False, cnpj=digits, company_name="", status="ERROR",
                    error=str(data.get("message", "CNPJ inválido.")),
                )
            situacao = str(data.get("situacao", "")).upper()
            company_name = str(data.get("nome", ""))
            if situacao != "ATIVA":
                return CnpjResult(
                    valid=False, cnpj=digits, company_name=company_name,
                    status=situacao,
                    error=f"CNPJ com situação: {situacao}. Apenas CNPJs ativos são aceitos.",
                )
            return CnpjResult(
                valid=True, cnpj=digits, company_name=company_name,
                status="ATIVA", error="",
            )
    except Exception as exc:
        logger.warning("receitaws_error", extra={"error": str(exc)})
        return None
