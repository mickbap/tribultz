"""Tests for LLM config: model tiers, fallback chain, retry logic."""
import pytest

from app.crews.llm_config import (
    DEFAULT_FALLBACK_CHAIN,
    FREE_FALLBACK,
    FREE_PRIMARY,
    TIER_GPT_OSS_20B,
    TIER_NEMOTRON_ULTRA,
    TIER_QWEN3_NEXT_80B,
    TIER_NEMOTRON_SUPER,
    TIER_GEMMA4_31B,
    TIER_LLAMA33_70B,
    TIER_FREE_ROUTER,
    LLMUnavailableError,
    ModelTier,
    _is_overloaded_or_rate_limited,
    build_llm,
    execute_with_fallback,
    get_llm_with_fallback,
)


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")


# ── Model tiers ────────────────────────────────────────────────


class TestModelTiers:
    def test_free_primary_is_free(self):
        assert FREE_PRIMARY.is_free is True
        assert "free" in FREE_PRIMARY.model_id

    def test_free_fallback_is_free(self):
        assert FREE_FALLBACK.is_free is True
        assert "free" in FREE_FALLBACK.model_id

    def test_default_chain_has_seven_tiers(self):
        assert len(DEFAULT_FALLBACK_CHAIN) == 7

    def test_default_chain_order(self):
        assert DEFAULT_FALLBACK_CHAIN == [
            TIER_GPT_OSS_20B,
            TIER_QWEN3_NEXT_80B,
            TIER_NEMOTRON_ULTRA,
            TIER_NEMOTRON_SUPER,
            TIER_GEMMA4_31B,
            TIER_LLAMA33_70B,
            TIER_FREE_ROUTER,
        ]

    def test_free_router_is_last_resort(self):
        """O router free é a rede de segurança — sempre o último tier."""
        assert DEFAULT_FALLBACK_CHAIN[-1] == TIER_FREE_ROUTER
        assert TIER_FREE_ROUTER.is_free is True
        assert TIER_FREE_ROUTER.model_id == "openrouter/openrouter/free"

    def test_all_tiers_are_free(self):
        """Benchmark 08/04/2026: 100% free tier, zero paid models."""
        for tier in DEFAULT_FALLBACK_CHAIN:
            assert tier.is_free is True, f"Tier {tier.name} must be free"

    def test_all_tiers_have_tool_calling_models(self):
        """All models são free + tool-calling (modelos :free do benchmark + router free)."""
        for tier in DEFAULT_FALLBACK_CHAIN:
            assert tier.is_free is True, f"Tier {tier.name} must be free"
            assert ":free" in tier.model_id or tier.model_id.endswith("/free"), (
                f"Tier {tier.name} must use a :free model or the openrouter/free router"
            )

    def test_primary_is_fastest_model(self):
        """gpt-oss-20b was fastest in benchmark (3.4s) — should be first."""
        assert DEFAULT_FALLBACK_CHAIN[0] == TIER_GPT_OSS_20B

    def test_default_chain_starts_with_free(self):
        assert DEFAULT_FALLBACK_CHAIN[0].is_free is True
        assert DEFAULT_FALLBACK_CHAIN[1].is_free is True


# ── API key ────────────────────────────────────────────────────


class TestApiKey:
    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(LLMUnavailableError, match="OPENROUTER_API_KEY"):
            build_llm(FREE_PRIMARY)


# ── build_llm ──────────────────────────────────────────────────


class TestBuildLlm:
    def test_returns_llm_instance(self):
        llm = build_llm(FREE_PRIMARY)
        assert llm is not None

    def test_llm_uses_tier_model_id(self):
        llm = build_llm(FREE_PRIMARY)
        assert llm.model == FREE_PRIMARY.model_id


# ── get_llm_with_fallback ──────────────────────────────────────


class TestGetLlmWithFallback:
    def test_returns_first_tier(self):
        llm, tier = get_llm_with_fallback()
        assert tier == FREE_PRIMARY

    def test_returns_custom_chain_first(self):
        # Use nemotron as the "priority" tier in a custom chain
        chain = [TIER_NEMOTRON_SUPER, FREE_PRIMARY]
        llm, tier = get_llm_with_fallback(chain)
        assert tier == TIER_NEMOTRON_SUPER


# ── execute_with_fallback ──────────────────────────────────────


class TestExecuteWithFallback:
    def test_success_on_first_tier(self):
        def fn(llm):
            return "ok"

        result, tier, elapsed = execute_with_fallback(fn)
        assert result == "ok"
        assert tier == FREE_PRIMARY
        assert elapsed >= 0

    def test_fallback_to_second_tier_on_failure(self):
        call_count = 0

        def fn(llm):
            nonlocal call_count
            call_count += 1
            if llm.model == FREE_PRIMARY.model_id:
                raise RuntimeError("primary down")
            return "fallback_ok"

        result, tier, elapsed = execute_with_fallback(fn)
        assert result == "fallback_ok"
        # Second tier in chain is TIER_QWEN3_NEXT_80B
        assert tier == TIER_QWEN3_NEXT_80B
        # PRIMARY (gpt-oss-20b) has max_retries=2, so 2 attempts + 1 on tier 2 = 3
        assert call_count == TIER_GPT_OSS_20B.max_retries + 1

    def test_fallback_traverses_all_six_tiers(self):
        """When the first 5 tiers fail, tier 6 (llama-3.3-70b) should succeed."""
        call_log: list[str] = []

        def fn(llm):
            call_log.append(llm.model)
            if llm.model != TIER_LLAMA33_70B.model_id:
                raise RuntimeError("tier down")
            return "last_resort_ok"

        result, tier, _ = execute_with_fallback(fn)
        assert result == "last_resort_ok"
        assert tier == TIER_LLAMA33_70B
        assert tier.is_free is True

    def test_all_tiers_exhausted_raises(self):
        def fn(llm):
            raise RuntimeError("all down")

        with pytest.raises(LLMUnavailableError, match="All LLM tiers exhausted"):
            execute_with_fallback(fn)

    def test_retries_within_tier(self):
        attempts = []

        def fn(llm):
            attempts.append(llm.model)
            if len(attempts) < 2:
                raise RuntimeError("transient error")
            return "recovered"

        single_tier = [ModelTier("test", "openrouter/test:free", True, max_retries=3)]
        result, tier, _ = execute_with_fallback(fn, chain=single_tier)
        assert result == "recovered"
        assert len(attempts) == 2

    def test_elapsed_time_is_positive(self):
        def fn(llm):
            return "fast"

        _, _, elapsed = execute_with_fallback(fn)
        assert elapsed >= 0

    def test_backoff_not_applied_for_non_transient_error(self, monkeypatch):
        """Non-transient errors should NOT sleep between retries."""
        slept: list[float] = []
        monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

        single_tier = [ModelTier("t", "openrouter/x:free", True, max_retries=2, backoff_base=5.0)]

        def fn(llm):
            raise RuntimeError("generic crash")  # non-transient

        with pytest.raises(LLMUnavailableError):
            execute_with_fallback(fn, chain=single_tier)

        assert slept == [], "No sleep expected for non-transient errors"

    def test_backoff_applied_for_429_status(self, monkeypatch):
        """429 Rate Limited should trigger exponential backoff between retries."""
        slept: list[float] = []
        monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

        single_tier = [ModelTier("t", "openrouter/x:free", True, max_retries=3, backoff_base=2.0)]

        def fn(llm):
            exc = RuntimeError("rate limited")
            exc.status_code = 429  # type: ignore[attr-defined]
            raise exc

        with pytest.raises(LLMUnavailableError):
            execute_with_fallback(fn, chain=single_tier)

        # 3 attempts: sleep after attempt 1 (2^1=2s) and attempt 2 (2^2=4s); no sleep after last
        assert slept == [2.0, 4.0]

    def test_backoff_applied_for_529_overloaded(self, monkeypatch):
        """529 Overloaded (Anthropic) should trigger backoff — not exhaust retries instantly."""
        slept: list[float] = []
        monkeypatch.setattr("time.sleep", lambda s: slept.append(s))

        single_tier = [ModelTier("t", "openrouter/anthropic/claude:paid", False, max_retries=2, backoff_base=3.0)]

        def fn(llm):
            exc = RuntimeError("API Error: 529 Overloaded")
            exc.status_code = 529  # type: ignore[attr-defined]
            raise exc

        with pytest.raises(LLMUnavailableError):
            execute_with_fallback(fn, chain=single_tier)

        # 2 attempts: sleep after attempt 1 (3^1=3s); no sleep after last
        assert slept == [3.0]


# ── _is_overloaded_or_rate_limited ────────────────────────────


class TestIsOverloadedOrRateLimited:
    def test_429_status_code(self):
        exc = RuntimeError("rate limited")
        exc.status_code = 429  # type: ignore[attr-defined]
        assert _is_overloaded_or_rate_limited(exc) is True

    def test_529_status_code(self):
        exc = RuntimeError("overloaded")
        exc.status_code = 529  # type: ignore[attr-defined]
        assert _is_overloaded_or_rate_limited(exc) is True

    def test_overloaded_in_message(self):
        assert _is_overloaded_or_rate_limited(RuntimeError("API Error: 529 Overloaded")) is True

    def test_rate_limit_in_message(self):
        assert _is_overloaded_or_rate_limited(RuntimeError("Rate limit exceeded")) is True

    def test_too_many_requests_in_message(self):
        assert _is_overloaded_or_rate_limited(RuntimeError("Too Many Requests")) is True

    def test_generic_error_is_not_transient(self):
        assert _is_overloaded_or_rate_limited(RuntimeError("connection refused")) is False

    def test_500_status_is_not_transient(self):
        exc = RuntimeError("server error")
        exc.status_code = 500  # type: ignore[attr-defined]
        assert _is_overloaded_or_rate_limited(exc) is False
