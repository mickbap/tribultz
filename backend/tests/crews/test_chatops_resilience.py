from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import cast

from app.crews import chatops_crew as chatops_module
from app.crews.chatops_crew import TribultzChatOpsCrew
from app.services.persistence.service import CrewPersistenceService


class FailingPersistenceService:
    def record_handoff(self, **_kwargs) -> None:
        raise ConnectionError("redis unavailable")


class FakeTask:
    def __init__(self) -> None:
        self.description = "{message}"


class FakeCrew:
    def __init__(self) -> None:
        self.tasks = [FakeTask()]

    def kickoff(self) -> str:
        return '{"response_markdown":"ok","evidence":[]}'


def test_record_handoff_degrades_to_volatile_only(caplog) -> None:
    crew = TribultzChatOpsCrew(
        tenant_id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        transaction_id="tx-m01-resilience",
        persistence_service=cast(CrewPersistenceService, FailingPersistenceService()),
    )

    with caplog.at_level(logging.ERROR):
        crew._record_handoff(agent_id="triage", task_id="classify_intent", task_status="QUEUED")

    assert any(getattr(record, "event", "") == "persistence_failure" for record in caplog.records)
    assert any(getattr(record, "task_status", "") == "VOLATILE_ONLY" for record in caplog.records)


def test_run_keeps_sync_flow_when_persistence_fails(monkeypatch, caplog) -> None:
    crew = TribultzChatOpsCrew(
        tenant_id="11111111-1111-1111-1111-111111111111",
        user_id="22222222-2222-2222-2222-222222222222",
        transaction_id="tx-m01-resilience-run",
        persistence_service=cast(CrewPersistenceService, FailingPersistenceService()),
    )

    monkeypatch.setattr(crew, "_build_crew", lambda llm: FakeCrew())

    def fake_execute_with_fallback(runner):
        output = runner(None)
        return output, SimpleNamespace(name="TEST", model_id="dummy-model"), 0.01

    monkeypatch.setattr(chatops_module, "execute_with_fallback", fake_execute_with_fallback)

    with caplog.at_level(logging.ERROR):
        result = crew.run("validar xml")

    assert result["response_markdown"] == "ok"
    assert any(getattr(record, "event", "") == "persistence_failure" for record in caplog.records)
