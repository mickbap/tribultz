from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from crewai import Agent, Crew, LLM, Memory, Process, Task
from dotenv import load_dotenv

from app.config import settings
from app.crews.tooling import CrewToolFactory, DefaultCrewToolFactory
from app.crews.llm_config import (
    LLMUnavailableError,
    execute_with_fallback,
)
from app.crews.memory_system import (
    RedisMemoryStorage,
    ScopedCrewMemory,
    build_openai_compatible_embedder,
)
from app.services.persistence import get_persistence_service
from app.services.persistence.service import CrewPersistenceService

load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_DIR = (
    Path(__file__).resolve().parents[3] / "crews" / "tribultz_chatops" / "config"
)


def _load_yaml(name: str) -> dict[str, Any]:
    with open(_CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_crew_output(raw: str) -> dict[str, Any]:
    """Extract JSON dict from the narrator's raw output string."""
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback: return raw text as response, no evidence
    return {"response_markdown": raw, "evidence": []}


class TribultzChatOpsCrew:
    """
    ChatOps crew: triage → operator → narrator.

    LLM selection uses tiered fallback (free models first, paid last).
    tenant_id and user_id are injected at construction and never passed
    through the LLM, ensuring tenant isolation.
    """

    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        transaction_id: str | None = None,
        tool_factory: CrewToolFactory | None = None,
        persistence_service: CrewPersistenceService | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._user_id = user_id
        self._transaction_id = transaction_id or str(uuid4())
        self._tool_factory = tool_factory or DefaultCrewToolFactory()
        self._persistence_service = persistence_service or get_persistence_service()

    def _memory_paths(self) -> dict[str, str]:
        base = f"/tenants/{self._tenant_id}"
        return {
            "short_term": f"{base}/transactions/{self._transaction_id}",
            "long_term": f"{base}/long_term/fiscal_classification",
            "entity": f"{base}/entities/fiscal_classification",
        }

    def _build_memory(self, llm: LLM) -> tuple[Memory, ScopedCrewMemory]:
        paths = self._memory_paths()
        shared_memory = Memory(
            llm=llm,
            storage=RedisMemoryStorage(redis_url=settings.REDIS_URL),
            embedder=build_openai_compatible_embedder(),
        )
        scoped_memory = ScopedCrewMemory(
            memory=shared_memory,
            recall_scopes=[paths["short_term"], paths["long_term"], paths["entity"]],
            write_scope=paths["short_term"],
            default_categories=["chatops", "fiscal_classification"],
            default_metadata={
                "tenant_id": self._tenant_id,
                "transaction_id": self._transaction_id,
                "crew": "chatops",
            },
            source=self._user_id,
        )
        return shared_memory, scoped_memory

    def _build_crew(self, llm: LLM) -> Crew:
        """Build the crew with a specific LLM instance."""
        agents_cfg = _load_yaml("agents.yaml")
        tasks_cfg = _load_yaml("tasks.yaml")

        tools_bundle = self._tool_factory.build_chatops_tools(
            tenant_id=self._tenant_id,
            user_id=self._user_id,
            transaction_id=self._transaction_id,
        )

        triage = Agent(
            role=agents_cfg["triage"]["role"],
            goal=agents_cfg["triage"]["goal"],
            backstory=agents_cfg["triage"]["backstory"],
            llm=llm,
            verbose=False,
        )
        operator = Agent(
            role=agents_cfg["operator"]["role"],
            goal=agents_cfg["operator"]["goal"],
            backstory=agents_cfg["operator"]["backstory"],
            tools=[
                tools_bundle.trigger_tool,
                tools_bundle.status_tool,
                tools_bundle.parse_nfse_tool,
                tools_bundle.validate_rules_tool,
                tools_bundle.parse_nfe_tool,
                tools_bundle.validate_ibscbs_tool,
            ],
            llm=llm,
            verbose=False,
        )
        narrator = Agent(
            role=agents_cfg["narrator"]["role"],
            goal=agents_cfg["narrator"]["goal"],
            backstory=agents_cfg["narrator"]["backstory"],
            llm=llm,
            verbose=False,
        )

        task_classify = Task(
            description=tasks_cfg["classify_intent"]["description"].format(
                message="{message}"
            ),
            expected_output=tasks_cfg["classify_intent"]["expected_output"],
            agent=triage,
        )
        task_trigger = Task(
            description=tasks_cfg["execute_operation"]["description"].format(
                tenant_id=self._tenant_id
            ),
            expected_output=tasks_cfg["execute_operation"]["expected_output"],
            agent=operator,
            context=[task_classify],
        )
        task_compose = Task(
            description=tasks_cfg["compose_response"]["description"],
            expected_output=tasks_cfg["compose_response"]["expected_output"],
            agent=narrator,
            context=[task_classify, task_trigger],
        )

        crew = Crew(
            agents=[triage, operator, narrator],
            tasks=[task_classify, task_trigger, task_compose],
            process=Process.sequential,
            verbose=False,
            memory=True,
        )
        try:
            shared_memory, scoped_memory = self._build_memory(llm)
            crew._memory = shared_memory
            triage.memory = scoped_memory
            operator.memory = scoped_memory
            narrator.memory = scoped_memory
        except Exception as exc:
            logger.warning("Crew memory unavailable for chatops; degrading gracefully: %s", exc)
            crew._memory = None
            triage.memory = None
            operator.memory = None
            narrator.memory = None
        return crew

    def run(self, message: str) -> dict[str, Any]:
        """Execute the crew with LLM fallback chain."""

        def _kickoff(llm: LLM) -> str:
            self._record_handoff(agent_id="triage", task_id="classify_intent", task_status="QUEUED")
            self._record_handoff(agent_id="operator", task_id="execute_operation", task_status="QUEUED")
            self._record_handoff(agent_id="narrator", task_id="compose_response", task_status="QUEUED")
            crew = self._build_crew(llm)
            crew.tasks[0].description = crew.tasks[0].description.replace(
                "{message}", message
            )
            result = crew.kickoff()
            self._record_handoff(agent_id="triage", task_id="classify_intent", task_status="COMPLETED")
            self._record_handoff(agent_id="operator", task_id="execute_operation", task_status="COMPLETED")
            self._record_handoff(agent_id="narrator", task_id="compose_response", task_status="COMPLETED")
            return str(result)

        try:
            raw_output, tier_used, elapsed = execute_with_fallback(_kickoff)
        except LLMUnavailableError as exc:
            # Distinguish overload (transient) from config/key errors (actionable)
            from app.crews.llm_config import _is_overloaded_or_rate_limited
            is_transient = _is_overloaded_or_rate_limited(exc.__cause__) if exc.__cause__ else False
            logger.error(
                "All LLM tiers exhausted for tenant=%s user=%s transient=%s error=%s",
                self._tenant_id,
                self._user_id,
                is_transient,
                str(exc)[:300],
            )
            self._record_handoff(agent_id="chatops", task_id="crew_execution", task_status="FAILED")
            if is_transient:
                msg = (
                    "⚠️ Os serviços de IA estão temporariamente sobrecarregados (erro 429/529). "
                    "Aguarde 1-2 minutos e tente novamente."
                )
            else:
                msg = (
                    "⚠️ Não foi possível processar sua solicitação no momento. "
                    "Se o problema persistir, entre em contato com o suporte."
                )
            return {"response_markdown": msg, "evidence": []}

        logger.info(
            "crew_execution_complete tenant=%s tier=%s model=%s elapsed=%.2fs",
            self._tenant_id,
            tier_used.name,
            tier_used.model_id,
            elapsed,
        )

        return _parse_crew_output(raw_output)

    def _record_handoff(self, *, agent_id: str, task_id: str, task_status: str) -> None:
        payload = {"agent_id": agent_id, "task_id": task_id, "task_status": task_status}
        logger.info(
            "agent_handoff",
            extra={
                "agent_id": agent_id,
                "task_id": task_id,
                "task_status": task_status,
                "tenant_id": self._tenant_id,
                "transaction_id": self._transaction_id,
            },
        )
        try:
            self._persistence_service.record_handoff(
                transaction_id=self._transaction_id,
                tenant_id=self._tenant_id,
                agent_id=agent_id,
                task_id=task_id,
                task_status=task_status,
                payload=payload,
            )
        except Exception as exc:
            logger.error(
                "Handoff persistence failed, degrading to volatile mode",
                extra={
                    "event": "persistence_failure",
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "task_status": "VOLATILE_ONLY",
                    "layer": "P1",
                    "error": str(exc),
                    "persistence_mode": "VOLATILE_ONLY",
                    "tenant_id": self._tenant_id,
                    "transaction_id": self._transaction_id,
                },
            )
