"""Tests for the Security Crew (SOC + CloudSec + SRE) — zero coverage before this file.

Crew.kickoff is monkeypatched globally (crewai.Crew) so real Agent/Task
construction (YAML-driven) runs for real, but no network call happens —
mirrors the seam already used in test_chatops_resilience.py.
"""

from __future__ import annotations

import pytest
from crewai import Crew

from app.crews.security_crew import TribultzSecurityCrew, _parse_output


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")


# ── _parse_output ────────────────────────────────────────────────


class TestParseOutput:
    def test_plain_json_object(self):
        assert _parse_output('{"report_markdown": "ok"}') == {"report_markdown": "ok"}

    def test_json_object_in_code_fence(self):
        raw = '```json\n{"alerts_found": 2}\n```'
        assert _parse_output(raw) == {"alerts_found": 2}

    def test_json_array_in_code_fence_wraps_in_alerts_key(self):
        raw = '```json\n[{"severity": "high"}]\n```'
        assert _parse_output(raw) == {"alerts": [{"severity": "high"}]}

    def test_non_json_falls_back_to_report_markdown(self):
        raw = "# Relatorio\nTudo certo."
        assert _parse_output(raw) == {"report_markdown": raw}

    def test_malformed_json_in_fence_falls_back(self):
        raw = "```json\n{not valid json}\n```"
        assert _parse_output(raw) == {"report_markdown": raw}


# ── TribultzSecurityCrew ───────────────────────────────────────────


class TestAnalyzeAccess:
    def test_returns_parsed_soc_output(self, monkeypatch):
        monkeypatch.setattr(
            Crew, "kickoff", lambda self: '{"alerts_found": 0, "summary": "sem anomalias"}'
        )
        crew = TribultzSecurityCrew(tenant_id="tenant-1")
        result = crew.analyze_access(log_data="[]")
        assert result == {"alerts_found": 0, "summary": "sem anomalias"}


class TestAuditStorage:
    def test_returns_parsed_cloudsec_output(self, monkeypatch):
        monkeypatch.setattr(
            Crew,
            "kickoff",
            lambda self: '{"summary": {"total": 7, "pass": 7, "fail": 0, "score_pct": 100}}',
        )
        crew = TribultzSecurityCrew(tenant_id="tenant-1")
        result = crew.audit_storage(storage_config="{}")
        assert result["summary"]["score_pct"] == 100


class TestExecutiveReport:
    def test_returns_parsed_markdown_report(self, monkeypatch):
        monkeypatch.setattr(Crew, "kickoff", lambda self: "# Resumo Executivo\nTudo em dia.")
        crew = TribultzSecurityCrew(tenant_id="tenant-1")
        result = crew.executive_report(
            soc_alerts="[]", cloudsec_audit="{}", report_period="2026-06-01 to 2026-07-01"
        )
        assert "Resumo Executivo" in result["report_markdown"]


class TestExecuteFallbackExhausted:
    def test_llm_unavailable_returns_error_dict(self, monkeypatch):
        """Crew.kickoff always raising exhausts every tier (no backoff — non-transient
        error) and _execute must degrade to an error dict, never raise to the caller."""

        def _always_fail(self):
            raise RuntimeError("network down")

        monkeypatch.setattr(Crew, "kickoff", _always_fail)
        crew = TribultzSecurityCrew(tenant_id="tenant-1")
        result = crew.analyze_access(log_data="[]")
        assert result == {
            "error": "Todos os modelos de IA estao temporariamente indisponiveis.",
        }
