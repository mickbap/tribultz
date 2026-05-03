"""NCM Auto-classify Service — LiteLLM + Redis cache.

Classifica descrições de produtos em NCM (8 dígitos) via LLM com fallback e cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import litellm

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_TTL = 60 * 60 * 24 * 7  # 7 dias

_SYSTEM_PROMPT = (
    "Você é um especialista em classificação fiscal brasileira (NCM/TIPI).\n"
    "Dado a descrição de um produto, identifique o código NCM de 8 dígitos mais adequado.\n"
    "Responda SOMENTE com JSON válido, sem markdown, sem explicações externas:\n"
    '{"ncm":"XXXXXXXX","confidence":0.0,"cClassTrib":"XX.XXX.XX","cest":"XXXXXXX","reasoning":"frase curta"}\n'
    "Regras:\n"
    "- ncm: exatamente 8 dígitos numéricos\n"
    "- confidence: 0.0–1.0 (probabilidade de acerto)\n"
    "- cClassTrib: código no formato XX.XXX.XX ou null se incerto\n"
    "- cest: 7 dígitos ou null se não aplicável\n"
    "- reasoning: 1 frase em português explicando a classificação"
)

_MODELS = [
    f"openrouter/{settings.LLM_FREE_PRIMARY}".replace("openrouter/openrouter/", "openrouter/"),
    f"openrouter/{settings.LLM_FREE_FALLBACK}".replace("openrouter/openrouter/", "openrouter/"),
]


def _cache_key(descricao: str) -> str:
    return f"ncm:suggest:{hashlib.md5(descricao.lower().strip().encode()).hexdigest()}"


def _call_llm(descricao: str) -> dict[str, Any]:
    last_err: Exception | None = None
    for model in _MODELS:
        try:
            resp = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": f"Produto: {descricao}"},
                ],
                api_base=settings.OPENROUTER_BASE_URL,
                api_key=settings.OPENROUTER_API_KEY,
                timeout=30,
                max_tokens=200,
                temperature=0.1,
            )
            content = resp.choices[0].message.content or ""
            return json.loads(content.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("NCM classify model %s failed: %s", model, exc)
            last_err = exc
    raise RuntimeError(f"Todos os modelos falharam: {last_err}") from last_err


def suggest(descricao: str, redis_client=None) -> dict[str, Any]:
    """Sugere NCM para a descrição dada. Usa cache Redis quando disponível."""
    key = _cache_key(descricao)

    if redis_client is not None:
        try:
            cached = redis_client.get(key)
            if cached:
                result = json.loads(cached)
                result["cached"] = True
                return result
        except Exception:  # noqa: BLE001
            pass

    result = _call_llm(descricao)
    result.setdefault("cached", False)

    # Normaliza campos obrigatórios
    result["ncm"] = str(result.get("ncm", "")).replace(".", "").replace("-", "")[:8].zfill(8)
    result["confidence"] = float(result.get("confidence", 0.5))
    result["cClassTrib"] = result.get("cClassTrib") or None
    result["cest"] = result.get("cest") or None
    result["reasoning"] = str(result.get("reasoning", ""))

    if redis_client is not None:
        try:
            redis_client.setex(key, _CACHE_TTL, json.dumps(result))
        except Exception:  # noqa: BLE001
            pass

    return result
