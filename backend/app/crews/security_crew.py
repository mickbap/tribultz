"""Tribultz Security Crew — SOC + CloudSec + SRE agents.

Status: Produção Interna — ver knowledge/engineering/crews.md (tribultz-brain).
Ferramenta operacional interna da Tribultz, não funcionalidade do produto.
Oferecer a clientes exige RFC própria antes de qualquer implementação.

Three specialized agents for enterprise security compliance:
- SOC Analyst: access monitoring, anomaly detection
- CloudSec Engineer: storage/infrastructure security audit
- SRE Lead: executive governance, periodic reports

Uses the same LLM fallback chain (app/crews/llm_config.py) as every other Crew.
"""

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

load_dotenv()

logger = logging.getLogger(__name__)

_CONFIG_DIR = (
    Path(__file__).resolve().parents[3] / "crews" / "tribultz_security" / "config"
)


def _load_yaml(name: str) -> dict[str, Any]:
    with open(_CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_output(raw: str) -> dict[str, Any]:
    """Extract JSON or Markdown from agent output."""
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
    match_arr = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
    if match_arr:
        try:
            return {"alerts": json.loads(match_arr.group(1))}
        except json.JSONDecodeError:
            pass
    return {"report_markdown": raw}


class TribultzSecurityCrew:
    """Security crew with SOC, CloudSec, and SRE agents."""

    def __init__(self, tenant_id: str) -> None:
        self._tenant_id = tenant_id

    def _build_agents(self, llm: LLM) -> dict[str, Agent]:
        agents_cfg = _load_yaml("agents.yaml")
        return {
            key: Agent(
                role=cfg["role"],
                goal=cfg["goal"],
                backstory=cfg["backstory"],
                llm=llm,
                verbose=cfg.get("verbose", False),
                allow_delegation=cfg.get("allow_delegation", False),
            )
            for key, cfg in agents_cfg.items()
        }

    # ── SOC: Analyze access logs ────────────────────────────
    def analyze_access(self, log_data: str) -> dict[str, Any]:
        """Run SOC analyst on access log data."""
        tasks_cfg = _load_yaml("tasks.yaml")

        def _run(llm: LLM) -> str:
            agents = self._build_agents(llm)
            task = Task(
                description=tasks_cfg["analyze_access_logs"]["description"].format(
                    tenant_id=self._tenant_id, log_data=log_data
                ),
                expected_output=tasks_cfg["analyze_access_logs"]["expected_output"],
                agent=agents["soc_analyst"],
            )
            crew = Crew(
                agents=[agents["soc_analyst"]],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            return str(crew.kickoff())

        return self._execute(_run, "analyze_access")

    # ── CloudSec: Audit storage ─────────────────────────────
    def audit_storage(self, storage_config: str) -> dict[str, Any]:
        """Run CloudSec engineer on storage configuration."""
        tasks_cfg = _load_yaml("tasks.yaml")

        def _run(llm: LLM) -> str:
            agents = self._build_agents(llm)
            task = Task(
                description=tasks_cfg["audit_storage_security"]["description"].format(
                    tenant_id=self._tenant_id, storage_config=storage_config
                ),
                expected_output=tasks_cfg["audit_storage_security"]["expected_output"],
                agent=agents["cloudsec_engineer"],
            )
            crew = Crew(
                agents=[agents["cloudsec_engineer"]],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            return str(crew.kickoff())

        return self._execute(_run, "audit_storage")

    # ── SRE: Executive report ───────────────────────────────
    def executive_report(
        self,
        soc_alerts: str,
        cloudsec_audit: str,
        report_period: str,
    ) -> dict[str, Any]:
        """Run full crew: SOC + CloudSec → SRE executive report."""
        tasks_cfg = _load_yaml("tasks.yaml")

        def _run(llm: LLM) -> str:
            agents = self._build_agents(llm)
            task = Task(
                description=tasks_cfg["generate_executive_report"]["description"].format(
                    soc_alerts=soc_alerts,
                    cloudsec_audit=cloudsec_audit,
                    report_period=report_period,
                ),
                expected_output=tasks_cfg["generate_executive_report"]["expected_output"],
                agent=agents["sre_lead"],
            )
            crew = Crew(
                agents=[agents["sre_lead"]],
                tasks=[task],
                process=Process.sequential,
                verbose=False,
            )
            return str(crew.kickoff())

        return self._execute(_run, "executive_report")

    def _execute(self, runner: Any, operation: str) -> dict[str, Any]:
        """Execute with LLM fallback and structured logging."""
        try:
            raw_output, tier_used, elapsed = execute_with_fallback(runner)
        except LLMUnavailableError:
            logger.error(
                "security_crew_llm_exhausted tenant=%s op=%s",
                self._tenant_id,
                operation,
            )
            return {
                "error": "Todos os modelos de IA estao temporariamente indisponiveis.",
            }

        logger.info(
            "security_crew_complete tenant=%s op=%s tier=%s model=%s elapsed=%.2fs",
            self._tenant_id,
            operation,
            tier_used.name,
            tier_used.model_id,
            elapsed,
        )

        return _parse_output(raw_output)
