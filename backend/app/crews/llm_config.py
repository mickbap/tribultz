"""
LLM configuration with tiered fallback for CrewAI agents.

Benchmark original em 08/04/2026 contra OpenRouter free tier (T1, T4-T7
abaixo sobrevivem desse benchmark). Revisão de disponibilidade em
17/07/2026: 2 dos 7 modelos originais (arcee-ai/trinity-large-preview,
openai/gpt-oss-120b) saíram do catálogo free do OpenRouter — toda vez que
T1 falhava, a cadeia perdia tempo tentando 2 tiers mortos antes de chegar
num vivo. Substituídos por T2/T3 novos: verificados **live + tool calling**
via `GET /api/v1/models` do OpenRouter nesta data, mas sem benchmark de
velocidade próprio (diferente de T1/T4-T7, que têm tempo medido).

Cadeia de fallback (7 tiers, diversificação de providers):
  T1  openai/gpt-oss-20b:free           3.4s  131K ctx  OpenAI  (US)     — mais rápido (bench 08/04/2026)
  T2  qwen/qwen3-next-80b-a3b:free      —     262K ctx  Alibaba (CN)     — substituto de trinity-large (revisão 17/07/2026)
  T3  nvidia/nemotron-3-ultra-550b:free —     1M  ctx   NVIDIA  (US)     — substituto de gpt-oss-120b, maior (revisão 17/07/2026)
  T4  nvidia/nemotron-3-super:free      11.6s 262K ctx  NVIDIA  (US)     — maior ctx (bench 08/04/2026)
  T5  google/gemma-4-31b:free           ~429  262K ctx  Google  (US/EU)  — qualidade (bench 08/04/2026)
  T6  meta-llama/llama-3.3-70b:free    ~429   65K ctx  Meta    (US)     — último recurso (bench 08/04/2026)
  T7  openrouter/free (router)           dyn   dyn      OpenRouter        — rede de segurança

T5 e T6 ficam em 429 sob alta carga mas recuperam após backoff.
T7 é o router free do OpenRouter: auto-seleciona um modelo free disponível
filtrando por tool calling — resiliente à volatilidade do free tier.
Nenhum modelo pago na cadeia — 100% free tier.

O catálogo free do OpenRouter tem alta rotatividade — reconfirmar
disponibilidade (`GET https://openrouter.ai/api/v1/models`, filtrar por
`id` terminando em `:free` e `supported_parameters` incluindo `tools`)
a cada trimestre ou ao notar 429/erro de modelo não encontrado recorrente.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from crewai import LLM

from app.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """All LLM tiers exhausted — no model available."""


def _is_overloaded_or_rate_limited(exc: BaseException) -> bool:
    """Detect transient 429/529 errors that warrant a retry with backoff."""
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    if status in (429, 529):
        return True
    msg = str(exc).lower()
    return "overloaded" in msg or "rate limit" in msg or "too many requests" in msg


@dataclass(frozen=True)
class ModelTier:
    name: str
    model_id: str
    is_free: bool
    max_retries: int = 2
    # seconds to wait between retries on transient errors (doubles each retry)
    backoff_base: float = 2.0


# ── Model registry — benchmark 08/04/2026 ──────────────────────
# Todos free, todos com tool calling confirmado.

TIER_GPT_OSS_20B = ModelTier(
    name="gpt-oss-20b",
    model_id="openrouter/openai/gpt-oss-20b:free",
    is_free=True,
    max_retries=2,
    backoff_base=2.0,
)

TIER_QWEN3_NEXT_80B = ModelTier(
    name="qwen3-next-80b",
    model_id="openrouter/qwen/qwen3-next-80b-a3b-instruct:free",
    is_free=True,
    max_retries=2,
    backoff_base=2.0,
)

TIER_NEMOTRON_ULTRA = ModelTier(
    name="nemotron-3-ultra-550b",
    model_id="openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    is_free=True,
    max_retries=2,
    backoff_base=2.0,
)

TIER_NEMOTRON_SUPER = ModelTier(
    name="nemotron-3-super-120b",
    model_id="openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    is_free=True,
    max_retries=2,
    backoff_base=2.0,
)

TIER_GEMMA4_31B = ModelTier(
    name="gemma-4-31b",
    model_id="openrouter/google/gemma-4-31b-it:free",
    is_free=True,
    max_retries=3,       # extra retry — popular, recebe mais 429
    backoff_base=2.0,
)

TIER_LLAMA33_70B = ModelTier(
    name="llama-3.3-70b",
    model_id="openrouter/meta-llama/llama-3.3-70b-instruct:free",
    is_free=True,
    max_retries=3,       # extra retry — popular, recebe mais 429
    backoff_base=2.0,
)

# Rede de segurança: router free do OpenRouter. Auto-seleciona um modelo free
# disponível filtrando por tool calling. Resiliente à volatilidade do free tier
# (modelos saem da lista sem aviso). Só é acionado se TODOS os tiers acima
# falharem — garante que a cadeia nunca "morre" e o custo continua R$ 0.
TIER_FREE_ROUTER = ModelTier(
    name="openrouter-free-router",
    model_id="openrouter/openrouter/free",
    is_free=True,
    max_retries=3,
    backoff_base=2.0,
)

# Cadeia padrão — ordem por confiabilidade observada no benchmark
# (T2/T3 revisados em 17/07/2026 — ver docstring do módulo)
DEFAULT_FALLBACK_CHAIN: list[ModelTier] = [
    TIER_GPT_OSS_20B,      # primário: mais rápido (3.4s), confiável
    TIER_QWEN3_NEXT_80B,   # 2º: provider alternativo (Alibaba/Qwen)
    TIER_NEMOTRON_ULTRA,   # 3º: maior e mais capaz (1M ctx)
    TIER_NEMOTRON_SUPER,   # 4º: 11.6s, 262K ctx, NVIDIA
    TIER_GEMMA4_31B,       # 5º: alta qualidade, pode 429
    TIER_LLAMA33_70B,      # 6º: último recurso, provado em PT-BR
    TIER_FREE_ROUTER,      # 7º: rede de segurança — router free auto-seleciona
]

# Aliases para compatibilidade retroativa
FREE_PRIMARY = TIER_GPT_OSS_20B
FREE_FALLBACK = TIER_QWEN3_NEXT_80B


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise LLMUnavailableError("OPENROUTER_API_KEY not set")
    return key


def build_llm(tier: ModelTier) -> LLM:
    """Create a CrewAI LLM instance for a given tier."""
    return LLM(
        model=tier.model_id,
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=_get_api_key(),
    )


def get_llm_with_fallback(
    chain: list[ModelTier] | None = None,
) -> tuple[LLM, ModelTier]:
    """
    Try to build an LLM from the fallback chain.
    Returns the first successfully constructed (llm, tier).
    In practice, construction rarely fails — the real fallback
    happens at execution time in execute_with_fallback().
    """
    tiers = chain or DEFAULT_FALLBACK_CHAIN
    api_key = _get_api_key()

    for tier in tiers:
        try:
            llm = LLM(
                model=tier.model_id,
                base_url=settings.OPENROUTER_BASE_URL,
                api_key=api_key,
            )
            logger.info("LLM selected: %s (free=%s)", tier.name, tier.is_free)
            return llm, tier
        except Exception:
            logger.warning("Failed to build LLM for tier %s, trying next", tier.name)
            continue

    raise LLMUnavailableError("All LLM tiers exhausted during construction")


def execute_with_fallback(
    fn: Any,
    *,
    chain: list[ModelTier] | None = None,
) -> tuple[Any, ModelTier, float]:
    """
    Execute a callable fn(llm) across the fallback chain.
    Returns (result, tier_used, elapsed_seconds).

    fn should accept a single LLM argument and return the result.
    If a tier fails after max_retries, moves to the next tier.
    Transient errors (429/529) trigger exponential backoff before retry.
    """
    tiers = chain or DEFAULT_FALLBACK_CHAIN
    api_key = _get_api_key()
    last_error: Exception | None = None

    for tier in tiers:
        llm = LLM(
            model=tier.model_id,
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=api_key,
        )
        for attempt in range(1, tier.max_retries + 1):
            t0 = time.monotonic()
            try:
                result = fn(llm)
                elapsed = time.monotonic() - t0
                logger.info(
                    "LLM call succeeded: tier=%s model=%s attempt=%d elapsed=%.2fs",
                    tier.name,
                    tier.model_id,
                    attempt,
                    elapsed,
                )
                return result, tier, elapsed
            except Exception as exc:
                elapsed = time.monotonic() - t0
                last_error = exc
                transient = _is_overloaded_or_rate_limited(exc)
                status = getattr(exc, "status_code", None) or getattr(exc, "status", "?")
                logger.warning(
                    "LLM call failed: tier=%s model=%s attempt=%d/%d "
                    "elapsed=%.2fs status=%s transient=%s error=%s",
                    tier.name,
                    tier.model_id,
                    attempt,
                    tier.max_retries,
                    elapsed,
                    status,
                    transient,
                    str(exc)[:300],
                )
                # Exponential backoff for 429/529 — give the model time to recover
                if transient and attempt < tier.max_retries:
                    backoff = tier.backoff_base ** attempt  # 2s → 4s → 8s
                    logger.info(
                        "Backing off %.0fs before retry (tier=%s attempt=%d status=%s)",
                        backoff, tier.name, attempt, status,
                    )
                    time.sleep(backoff)

    raise LLMUnavailableError(
        f"All LLM tiers exhausted. Last error: {last_error}"
    )
