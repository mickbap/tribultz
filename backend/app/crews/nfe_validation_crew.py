from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

from app.crews.tooling import CrewToolFactory, DefaultCrewToolFactory
from app.crews.llm_config import (
    LLMUnavailableError,
    execute_with_fallback,
)

load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_DIR = (
    Path(__file__).resolve().parents[3] / "crews" / "tribultz_nfe_validation" / "config"
)


def _load_yaml(name: str) -> dict[str, Any]:
    with open(_CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_crew_output(raw: str) -> dict[str, Any]:
    """Extract JSON dict from the reporter's raw output string."""
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
    return {"response_markdown": raw, "evidence": []}


class NFeValidationCrew:
    """
    NF-e/NFC-e validation crew: parser → validator → reporter.

    Pipeline:
      1. nfe_parser — Extracts IBSCBS fields from XML (parse_nfe_xml tool)
      2. ibscbs_validator — Applies 14 NT 2025.002-RTC rules (validate_ibscbs_rules tool)
      3. nfe_reporter — Composes Markdown report with findings and recommendations

    tenant_id is injected at construction and never passed through the LLM.
    """

    def __init__(
        self,
        tenant_id: str,
        transaction_id: str | None = None,
        tool_factory: CrewToolFactory | None = None,
    ) -> None:
        self._tenant_id = tenant_id
        self._transaction_id = transaction_id or str(uuid4())
        self._tool_factory = tool_factory or DefaultCrewToolFactory()

    def _build_crew(self, llm: LLM, xml_content: str) -> Crew:
        """Build the crew with a specific LLM instance."""
        agents_cfg = _load_yaml("agents.yaml")
        tasks_cfg = _load_yaml("tasks.yaml")

        tools_bundle = self._tool_factory.build_nfe_validation_tools(
            tenant_id=self._tenant_id,
            transaction_id=self._transaction_id,
        )

        # Agent 1: NF-e Parser
        parser_agent = Agent(
            role=agents_cfg["nfe_parser"]["role"],
            goal=agents_cfg["nfe_parser"]["goal"],
            backstory=agents_cfg["nfe_parser"]["backstory"],
            tools=[tools_bundle.parse_nfe_tool],
            llm=llm,
            verbose=False,
        )

        # Agent 2: IBSCBS Validator
        validator_agent = Agent(
            role=agents_cfg["ibscbs_validator"]["role"],
            goal=agents_cfg["ibscbs_validator"]["goal"],
            backstory=agents_cfg["ibscbs_validator"]["backstory"],
            tools=[tools_bundle.validate_ibscbs_tool],
            llm=llm,
            verbose=False,
        )

        # Agent 3: Report Composer
        reporter_agent = Agent(
            role=agents_cfg["nfe_reporter"]["role"],
            goal=agents_cfg["nfe_reporter"]["goal"],
            backstory=agents_cfg["nfe_reporter"]["backstory"],
            llm=llm,
            verbose=False,
        )

        # Task 1: Parse XML
        task_parse = Task(
            description=tasks_cfg["parse_nfe_xml"]["description"].format(
                xml_content=xml_content
            ),
            expected_output=tasks_cfg["parse_nfe_xml"]["expected_output"],
            agent=parser_agent,
        )

        # Task 2: Validate (depends on parse)
        task_validate = Task(
            description=tasks_cfg["validate_ibscbs"]["description"],
            expected_output=tasks_cfg["validate_ibscbs"]["expected_output"],
            agent=validator_agent,
            context=[task_parse],
        )

        # Task 3: Report (depends on parse + validate)
        task_report = Task(
            description=tasks_cfg["compose_nfe_report"]["description"],
            expected_output=tasks_cfg["compose_nfe_report"]["expected_output"],
            agent=reporter_agent,
            context=[task_parse, task_validate],
        )

        return Crew(
            agents=[parser_agent, validator_agent, reporter_agent],
            tasks=[task_parse, task_validate, task_report],
            process=Process.sequential,
            verbose=False,
        )

    def run(self, xml_content: str) -> dict[str, Any]:
        """Execute the NF-e validation crew with LLM fallback chain."""

        def _kickoff(llm: LLM) -> str:
            logger.info(
                "agent_handoff",
                extra={
                    "agent_id": "nfe_parser",
                    "task_id": "parse_nfe_xml",
                    "task_status": "QUEUED",
                    "tenant_id": self._tenant_id,
                    "transaction_id": self._transaction_id,
                },
            )
            logger.info(
                "agent_handoff",
                extra={
                    "agent_id": "ibscbs_validator",
                    "task_id": "validate_ibscbs",
                    "task_status": "QUEUED",
                    "tenant_id": self._tenant_id,
                    "transaction_id": self._transaction_id,
                },
            )
            logger.info(
                "agent_handoff",
                extra={
                    "agent_id": "nfe_reporter",
                    "task_id": "compose_nfe_report",
                    "task_status": "QUEUED",
                    "tenant_id": self._tenant_id,
                    "transaction_id": self._transaction_id,
                },
            )
            crew = self._build_crew(llm, xml_content)
            result = crew.kickoff()
            logger.info(
                "agent_handoff",
                extra={
                    "agent_id": "nfe_reporter",
                    "task_id": "compose_nfe_report",
                    "task_status": "COMPLETED",
                    "tenant_id": self._tenant_id,
                    "transaction_id": self._transaction_id,
                },
            )
            return str(result)

        try:
            raw_output, tier_used, elapsed = execute_with_fallback(_kickoff)
        except LLMUnavailableError:
            logger.error(
                "All LLM tiers exhausted for NF-e validation tenant=%s",
                self._tenant_id,
            )
            return {
                "response_markdown": (
                    "Todos os modelos de IA estao temporariamente indisponiveis. "
                    "Tente novamente em alguns minutos."
                ),
                "evidence": [],
            }

        logger.info(
            "nfe_validation_crew_complete tenant=%s tier=%s model=%s elapsed=%.2fs",
            self._tenant_id,
            tier_used.name,
            tier_used.model_id,
            elapsed,
        )

        return _parse_crew_output(raw_output)
