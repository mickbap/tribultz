"""
LLM configuration with tiered fallback for CrewAI agents.

Model tiers (evaluated March 2026 via OpenRouter):
  - FREE_PRIMARY:  google/gemini-2.0-flash-exp:free  (1M ctx, good tool calling)
  - FREE_FALLBACK: qwen/qwen3-coder-480b-a35b-instruct:free (262K ctx, strong JSON)
  - PAID_FALLBACK: openrouter/anthropic/claude-3-5-sonnet (best quality, paid)

The fallback chain tries each tier in order. If all fail, raises LLMUnavailableError.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from crewai import LLM

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LLMUnavailableError(RuntimeError):
    """All LLM tiers exhausted — no model available."""


@dataclass(frozen=True)
class ModelTier:
    name: str
    model_id: str
    is_free: bool
    max_retries: int = 2


# ── Model registry ─────────────────────────────────────────────

FREE_PRIMARY = ModelTier(
    name="gemini-2.0-flash-free",
    model_id="openrouter/google/gemini-2.0-flash-exp:free",
    is_free=True,
    max_retries=2,
)

FREE_FALLBACK = ModelTier(
    name="qwen3-coder-free",
    model_id="openrouter/qwen/qwen3-coder-480b-a35b-instruct:free",
    is_free=True,
    max_retries=1,
)

PAID_FALLBACK = ModelTier(
    name="claude-3.5-sonnet",
    model_id="openrouter/anthropic/claude-3-5-sonnet",
    is_free=False,
    max_retries=1,
)

DEFAULT_FALLBACK_CHAIN: list[ModelTier] = [FREE_PRIMARY, FREE_FALLBACK, PAID_FALLBACK]


def _get_api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise LLMUnavailableError("OPENROUTER_API_KEY not set")
    return key


def build_llm(tier: ModelTier) -> LLM:
    """Create a CrewAI LLM instance for a given tier."""
    return LLM(
        model=tier.model_id,
        base_url=OPENROUTER_BASE_URL,
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
                base_url=OPENROUTER_BASE_URL,
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
    """
    tiers = chain or DEFAULT_FALLBACK_CHAIN
    api_key = _get_api_key()
    last_error: Exception | None = None

    for tier in tiers:
        llm = LLM(
            model=tier.model_id,
            base_url=OPENROUTER_BASE_URL,
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
                logger.warning(
                    "LLM call failed: tier=%s model=%s attempt=%d/%d elapsed=%.2fs error=%s",
                    tier.name,
                    tier.model_id,
                    attempt,
                    tier.max_retries,
                    elapsed,
                    str(exc)[:200],
                )

    raise LLMUnavailableError(
        f"All LLM tiers exhausted. Last error: {last_error}"
    )
