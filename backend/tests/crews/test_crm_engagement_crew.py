"""Tests for CRMEngagementCrew (dunning/win-back emails) — zero coverage before this file.

Crew.kickoff is monkeypatched globally (crewai.Crew) for the run() tests —
same seam used in test_chatops_resilience.py and test_security_crew.py.
"""

from __future__ import annotations

import pytest
from crewai import LLM, Crew

from app.crews.crm_engagement_crew import _EVENT_GUIDANCE, CRMEngagementCrew


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")


def _make_crew(event_type: str = "payment_overdue") -> CRMEngagementCrew:
    return CRMEngagementCrew(
        user_id="user-1",
        tenant_id="tenant-1",
        event_type=event_type,
        to_email="cliente@example.com",
        user_name="Maria Silva",
        company_name="Empresa Exemplo Ltda",
        transaction_id="tx-crm-test",
    )


# ── Event guidance ─────────────────────────────────────────────


class TestEventGuidance:
    def test_payment_overdue_and_win_back_have_distinct_copy(self):
        overdue = _EVENT_GUIDANCE["payment_overdue"]
        cancelled = _EVENT_GUIDANCE["subscription_cancelled"]
        assert overdue["tone"] != cancelled["tone"]
        assert overdue["subject_hint"] != cancelled["subject_hint"]

    def test_known_event_types_select_matching_guidance(self):
        assert _make_crew("payment_overdue")._guidance == _EVENT_GUIDANCE["payment_overdue"]
        assert (
            _make_crew("subscription_cancelled")._guidance
            == _EVENT_GUIDANCE["subscription_cancelled"]
        )

    def test_unknown_event_type_falls_back_to_payment_overdue(self):
        crew = _make_crew("some_unmapped_event")
        assert crew._guidance == _EVENT_GUIDANCE["payment_overdue"]


# ── _build_crew wiring ──────────────────────────────────────────


class TestBuildCrewWiring:
    def test_three_agents_three_tasks_in_order(self):
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        assert [a.role for a in crew.agents] == [
            "CRM Analyst",
            "Email Copywriter",
            "CRM Executor",
        ]
        assert len(crew.tasks) == 3

    def test_analyst_has_only_context_tool(self):
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        analyst = crew.agents[0]
        assert [t.name for t in analyst.tools or []] == ["get_customer_context"]

    def test_executor_has_email_and_hubspot_tools(self):
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        executor = crew.agents[2]
        assert [t.name for t in executor.tools or []] == ["send_email", "hubspot_log_note"]

    def test_copywriter_has_no_tools(self):
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        assert crew.agents[1].tools == []

    def test_task_dependency_chain(self):
        """compose depends on analyze; send depends on compose."""
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        task_analyze, task_compose, task_send = crew.tasks
        assert task_compose.context == [task_analyze]
        assert task_send.context == [task_compose]

    def test_crew_has_no_memory(self):
        """CRM crew is one-shot — docstring says 'No memory'."""
        llm = LLM(model="openrouter/test:free", api_key="test-key-123")
        crew = _make_crew()._build_crew(llm)
        assert crew.memory is False


# ── run() ────────────────────────────────────────────────────────


class TestRun:
    def test_success_returns_completed_status(self, monkeypatch):
        monkeypatch.setattr(Crew, "kickoff", lambda self: '{"email_sent": true, "hubspot_logged": true}')
        crew = _make_crew("subscription_cancelled")
        result = crew.run()
        assert result["status"] == "crew_completed"
        assert result["event_type"] == "subscription_cancelled"
        assert "email_sent" in result["output"]

    def test_llm_unavailable_returns_llm_unavailable_status(self, monkeypatch):
        def _always_fail(self):
            raise RuntimeError("network down")

        monkeypatch.setattr(Crew, "kickoff", _always_fail)
        crew = _make_crew()
        result = crew.run()
        assert result == {"status": "llm_unavailable", "event_type": "payment_overdue"}
