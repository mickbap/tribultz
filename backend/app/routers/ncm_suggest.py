"""NCM Auto-classify — POST /api/v1/public/ncm/suggest (#170).

Freemium: 10 classificações/IP/dia sem autenticação.
Cache Redis 30 dias (mapeamento NCM-cClassTrib é estável).
LLM via OpenRouter com fallback em 3 tiers.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from datetime import date
from typing import Optional, cast

import litellm
from litellm.types.utils import Choices as LiteLLMChoices
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, field_validator

from app.data.ncm_codes import is_valid_ncm
from app.data.ncm_cclasstrib_table import resolve_cclasstrib

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ncm-suggest"])

_DAILY_LIMIT = 10
_CACHE_TTL_SECONDS = 86_400 * 30  # 30 days

_LLM_MODELS = [
    "openrouter/openai/gpt-oss-20b:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    # gemma-4-31b-it:free ficou persistentemente rate-limited (429) em produção
    # 2026-07-26 — troca por outra variante Gemma, endpoint upstream diferente.
    "openrouter/google/gemma-4-26b-a4b-it:free",
]

_SYSTEM_PROMPT = """\
Você é um especialista em classificação NCM (Nomenclatura Comum do Mercosul) \
para a legislação tributária brasileira (TIPI — Decreto 11.158/2022).

Dado a descrição de um produto em português, retorne o código NCM de 8 dígitos \
mais adequado conforme a TIPI vigente.

Responda SOMENTE com JSON válido, sem markdown, sem texto adicional:
{
  "ncm": "XXXXXXXX",
  "ncm_descricao": "descrição resumida do capítulo/posição NCM",
  "confidence": 0.95
}

Regras:
- ncm: exatamente 8 dígitos numéricos, sem pontos ou hífens
- confidence: 0.0–1.0 (use < 0.70 quando o produto for ambíguo ou você não tiver certeza)
- Se o produto for muito vago, use confidence < 0.50 e o NCM mais provável do capítulo

Exemplos:
{"descricao": "Carne bovina traseira resfriada"} \
→ {"ncm": "02013000", "ncm_descricao": "Carnes bovinas frescas ou refrigeradas", "confidence": 0.95}
{"descricao": "Smartphone Samsung Galaxy 15"} \
→ {"ncm": "85171200", "ncm_descricao": "Telefones para redes celulares/sem fio", "confidence": 0.92}
{"descricao": "Serviço de consultoria"} \
→ {"ncm": "98010100", "ncm_descricao": "Serviços profissionais", "confidence": 0.40}
"""


# ── Schemas ────────────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    descricao: str

    @field_validator("descricao")
    @classmethod
    def validate_descricao(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Descrição muito curta (mínimo 3 caracteres)")
        if len(v) > 500:
            raise ValueError("Descrição muito longa (máximo 500 caracteres)")
        return v


class CClassTribCandidato(BaseModel):
    """Candidato de cClassTrib (6 dígitos) para uma NCM, com base legal (RF-A2)."""
    codigo: str          # 6 dígitos, tabela oficial SVRS
    descricao: str
    base_legal: str      # Anexo da tabela oficial (LC 214/2025)
    legislacao: str = ""  # link da legislação (planalto)


class SuggestResponse(BaseModel):
    ncm: str
    ncm_descricao: str
    confidence: float
    # cClassTrib: NUNCA taxonomia de produto (RF-A1). null quando não há mapeamento
    # 6-díg confiável — usar candidatos/status em vez de palpite único (RF-A2/A3).
    cClassTrib: Optional[str] = None
    cclasstrib_candidatos: list[CClassTribCandidato] = []
    # "requer_validacao" (sem mapeamento confiável) | "multiplos" (NCM admite vários)
    # | "unico" (1:1). Resposta de cClassTrib é sempre SUGESTÃO a validar, não veredito.
    cclasstrib_status: str = "requer_validacao"
    cest: None = None
    rate_source: str = "ncm_ai"
    aviso: Optional[str] = None


# ── Redis helpers (best-effort — falls back gracefully) ────────────────────────

def _get_redis():  # type: ignore[return]
    import redis as redis_lib
    from app.config import settings
    return redis_lib.from_url(settings.REDIS_URL, decode_responses=True)


def _rate_check(client_ip: str) -> None:
    try:
        r = _get_redis()
        today = date.today().isoformat()
        key = f"ncm_suggest_rate:{client_ip}:{today}"
        count = cast(int, r.incr(key))
        if count == 1:
            r.expire(key, 86_400)
        if count > _DAILY_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Limite de {_DAILY_LIMIT} classificações gratuitas por dia atingido. "
                    "Crie uma conta para ampliar o limite."
                ),
                headers={"Retry-After": "86400"},
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis unavailable — allow through


def _cache_get(key: str) -> Optional[dict]:
    try:
        raw = cast(Optional[str], _get_redis().get(key))
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, value: dict) -> None:
    try:
        _get_redis().setex(key, _CACHE_TTL_SECONDS, json.dumps(value))
    except Exception:
        pass


# ── LLM call with 3-tier fallback ─────────────────────────────────────────────

def _llm_classify(descricao: str) -> dict:
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de classificação temporariamente indisponível.",
        )

    for model in _LLM_MODELS:
        try:
            resp = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Produto: {descricao}"},
                ],
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                # 150 cortava modelos de raciocínio (gpt-oss, nemotron) no meio do
                # "thinking", antes de emitirem o JSON final (confirmado em log de
                # produção, 2026-07-26) — 500 dá espaço pro raciocínio + resposta.
                max_tokens=500,
                temperature=0.1,
                timeout=20,
            )
            model_resp = cast(litellm.ModelResponse, resp)
            choice = cast(LiteLLMChoices, model_resp.choices[0])
            content = (choice.message.content or "").strip()
            match = re.search(r"\{[^}]+\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                if "ncm" in data and "confidence" in data:
                    logger.info("ncm_suggest: model=%s ncm=%s confidence=%s", model, data.get("ncm"), data.get("confidence"))
                    return data
            logger.warning("ncm_suggest: model=%s returned no usable JSON: %s", model, content[:200])
        except Exception as exc:
            logger.warning("ncm_suggest: model=%s failed: %s", model, str(exc)[:200])
            continue

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Classificação indisponível no momento. Tente novamente em alguns segundos.",
    )


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post(
    "/api/v1/public/ncm/suggest",
    response_model=SuggestResponse,
    summary="Sugerir NCM a partir de descrição do produto (freemium, 10/dia por IP)",
)
def suggest_ncm(
    payload: SuggestRequest,
    request: Request,
) -> SuggestResponse:
    client_ip = (request.client.host if request.client else "unknown")
    _rate_check(client_ip)

    # Cache key: SHA-256 de descrição normalizada (case-insensitive, espaços colapsados)
    normalized = " ".join(payload.descricao.lower().split())
    cache_key = f"ncm_suggest:v3:{hashlib.sha256(normalized.encode()).hexdigest()[:24]}"

    cached = _cache_get(cache_key)
    if cached:
        return SuggestResponse(**cached)

    llm_result = _llm_classify(normalized)

    raw_ncm = str(llm_result.get("ncm", "")).strip().replace(".", "").replace("-", "")
    ncm = raw_ncm.zfill(8)[:8]
    confidence = min(max(float(llm_result.get("confidence", 0.5)), 0.0), 1.0)
    ncm_descricao = str(llm_result.get("ncm_descricao", "")).strip()

    # Se o NCM não é válido na tabela TIPI, abaixa confiança
    if not is_valid_ncm(ncm):
        confidence = min(confidence, 0.50)
        logger.warning("ncm_suggest: NCM %s not in TIPI table — confidence capped at 0.50", ncm)

    # cClassTrib via mapeamento oficial NCM→cClassTrib (anexos SVRS, app/data/ncm_cclasstrib.json).
    # NUNCA taxonomia de produto (RF-A1); candidatos a validar, não veredito (RF-A2);
    # null honesto quando não há mapeamento (RF-A3). Para NCM multi-mapeada, cClassTrib
    # fica null e os candidatos vêm na lista (palpite único confiante é o que gera a 1024).
    cclasstrib, cc_candidatos, cc_status = resolve_cclasstrib(ncm)

    aviso: str | None = None
    if confidence < 0.70:
        aviso = "Confiança baixa — confirme o NCM com seu contador antes de usar em NF-e."

    result: dict = {
        "ncm": ncm,
        "ncm_descricao": ncm_descricao,
        "confidence": round(confidence, 2),
        "cClassTrib": cclasstrib,
        "cclasstrib_candidatos": cc_candidatos,
        "cclasstrib_status": cc_status,
        "cest": None,
        "rate_source": "ncm_ai",
        "aviso": aviso,
    }
    _cache_set(cache_key, result)
    return SuggestResponse(**result)
