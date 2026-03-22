from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

from app.crews.llm_config import (
    LLMUnavailableError,
    execute_with_fallback,
)
from app.crews.tools.get_job_status_tool import GetJobStatusTool
from app.crews.tools.parse_nfse_xml_tool import ParseNFSeXMLTool
from app.crews.tools.trigger_task_a_tool import TriggerTaskATool
from app.crews.tools.validate_fiscal_rules_tool import ValidateFiscalRulesTool

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

    def __init__(self, tenant_id: str, user_id: str) -> None:
        self._tenant_id = tenant_id
        self._user_id = user_id

    def _build_crew(self, llm: LLM) -> Crew:
        """Build the crew with a specific LLM instance."""
        agents_cfg = _load_yaml("agents.yaml")
        tasks_cfg = _load_yaml("tasks.yaml")

        trigger_tool = TriggerTaskATool(
            tenant_id=self._tenant_id, user_id=self._user_id
        )
        status_tool = GetJobStatusTool(tenant_id=self._tenant_id)
        parse_nfse_tool = ParseNFSeXMLTool(tenant_id=self._tenant_id)
        validate_rules_tool = ValidateFiscalRulesTool()

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
            tools=[trigger_tool, status_tool, parse_nfse_tool, validate_rules_tool],
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

        return Crew(
            agents=[triage, operator, narrator],
            tasks=[task_classify, task_trigger, task_compose],
            process=Process.sequential,
            verbose=False,
        )

    def run(self, message: str) -> dict[str, Any]:
        """Execute the crew with LLM fallback chain."""

        def _kickoff(llm: LLM) -> str:
            crew = self._build_crew(llm)
            # Inject message into the first task's description
            crew.tasks[0].description = crew.tasks[0].description.replace(
                "{message}", message
            )
            result = crew.kickoff()
            return str(result)

        try:
            raw_output, tier_used, elapsed = execute_with_fallback(_kickoff)
        except LLMUnavailableError:
            logger.error(
                "All LLM tiers exhausted for tenant=%s user=%s",
                self._tenant_id,
                self._user_id,
            )
            return {
                "response_markdown": (
                    "Todos os modelos de IA estao temporariamente indisponiveis. "
                    "Tente novamente em alguns minutos."
                ),
                "evidence": [],
            }

        logger.info(
            "crew_execution_complete tenant=%s tier=%s model=%s elapsed=%.2fs",
            self._tenant_id,
            tier_used.name,
            tier_used.model_id,
            elapsed,
        )

        return _parse_crew_output(raw_output)
