"""Tests for LLM config: model tiers, fallback chain, retry logic."""
import pytest

from app.crews.llm_config import (
    DEFAULT_FALLBACK_CHAIN,
    FREE_FALLBACK,
    FREE_PRIMARY,
    PAID_FALLBACK,
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

    def test_paid_fallback_is_not_free(self):
        assert PAID_FALLBACK.is_free is False

    def test_default_chain_order(self):
        assert DEFAULT_FALLBACK_CHAIN == [FREE_PRIMARY, FREE_FALLBACK, PAID_FALLBACK]

    def test_default_chain_starts_with_free(self):
        assert DEFAULT_FALLBACK_CHAIN[0].is_free is True
        assert DEFAULT_FALLBACK_CHAIN[1].is_free is True

    def test_default_chain_ends_with_paid(self):
        assert DEFAULT_FALLBACK_CHAIN[-1].is_free is False


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
        chain = [PAID_FALLBACK, FREE_PRIMARY]
        llm, tier = get_llm_with_fallback(chain)
        assert tier == PAID_FALLBACK


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
        assert tier == FREE_FALLBACK
        # PRIMARY has max_retries=3 (free model overloads are common),
        # so 3 attempts + 1 on fallback = 4
        assert call_count == FREE_PRIMARY.max_retries + 1

    def test_fallback_to_paid_when_all_free_fail(self):
        def fn(llm):
            if "free" in llm.model or ":free" in llm.model:
                raise RuntimeError("free model down")
            return "paid_ok"

        result, tier, _ = execute_with_fallback(fn)
        assert result == "paid_ok"
        assert tier == PAID_FALLBACK
        assert tier.is_free is False

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
