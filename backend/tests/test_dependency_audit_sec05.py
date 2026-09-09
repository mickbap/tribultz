"""SEC-05 contracts for dependency scanner execution and finding routing."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / ".github" / "scripts" / "dependency_audit.py"
WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "dependency-audit.yml"


@pytest.fixture(scope="module")
def audit_module():
    spec = importlib.util.spec_from_file_location("dependency_audit_under_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def pip_payload(*vulns):
    return {
        "dependencies": [
            {"name": "weasyprint", "version": "68.0", "vulns": list(vulns)}
        ]
    }


def npm_payload(*, vulnerabilities=None):
    return {
        "auditReportVersion": 2,
        "vulnerabilities": vulnerabilities or {},
        "metadata": {"vulnerabilities": {"total": len(vulnerabilities or {})}},
    }


def evidence(
    audit_module,
    *,
    pip_raw,
    pip_exit=0,
    pip_timed_out=False,
    npm_raw=None,
    npm_exit=0,
):
    import json

    return audit_module.analyze(
        {
            "pip-audit": (
                pip_raw if isinstance(pip_raw, str) else json.dumps(pip_raw),
                {"exit_code": pip_exit, "timed_out": pip_timed_out},
            ),
            "npm-audit": (
                json.dumps(npm_raw if npm_raw is not None else npm_payload()),
                {"exit_code": npm_exit},
            ),
        }
    )


def test_scanner_error_is_operational_failure(audit_module):
    result = evidence(audit_module, pip_raw=pip_payload(), pip_exit=2)
    assert result["execution_state"] == audit_module.OPERATIONAL_FAILURE
    assert result["gate_decision"] == "FAIL_CLOSED_OPERATIONAL_FAILURE"
    assert result["counts"]["operational_failures"] == 1


def test_scanner_timeout_is_operational_failure(audit_module):
    result = evidence(
        audit_module,
        pip_raw=pip_payload(),
        pip_exit=124,
        pip_timed_out=True,
    )
    assert result["execution_state"] == audit_module.OPERATIONAL_FAILURE
    assert result["gate_decision"] == "FAIL_CLOSED_OPERATIONAL_FAILURE"
    assert "scanner excedeu timeout" in result["operational_failures"][0]["reasons"]


def test_invalid_json_is_operational_failure(audit_module):
    result = evidence(audit_module, pip_raw="{broken", pip_exit=1)
    assert result["execution_state"] == audit_module.OPERATIONAL_FAILURE
    assert "JSON inválido" in result["operational_failures"][0]["reasons"][0]


def test_valid_zero_is_valid_no_findings(audit_module):
    result = evidence(audit_module, pip_raw=pip_payload())
    assert result["execution_state"] == audit_module.VALID_NO_FINDINGS
    assert result["counts"]["total"] == 0


def test_valid_fixable_finding_is_routed(audit_module):
    result = evidence(
        audit_module,
        pip_raw=pip_payload(
            {"id": "PYSEC-2026-1", "aliases": ["CVE-2026-1"], "fix_versions": ["69.0"]}
        ),
        pip_exit=1,
    )
    assert result["execution_state"] == audit_module.VALID_WITH_FINDINGS
    assert result["counts"]["fixable"] == 1
    routing = audit_module.render_findings(result["findings"], fixable=True)
    assert "PYSEC-2026-1" in routing
    assert "69.0" in routing


def test_valid_no_patch_remains_finding_with_qualified_routing(audit_module):
    result = evidence(
        audit_module,
        pip_raw=pip_payload(
            {"id": "PYSEC-2026-2", "aliases": [], "fix_versions": []}
        ),
        pip_exit=1,
    )
    assert result["counts"]["no_patch_declared_or_unknown"] == 1
    routing = audit_module.render_findings(result["findings"], fixable=False)
    assert "scanner não declarou patch" in routing
    assert "não existe correção" not in routing


def test_repeat_finding_is_deduplicated(audit_module):
    duplicate = {"id": "PYSEC-2026-3", "aliases": [], "fix_versions": ["2.0"]}
    result = evidence(audit_module, pip_raw=pip_payload(duplicate, duplicate), pip_exit=1)
    assert result["counts"]["total"] == 1
    assert len(result["findings"]) == 1


def test_invalid_schema_and_empty_output_fail_closed(audit_module):
    invalid = evidence(audit_module, pip_raw={"dependencies": "not-a-list"})
    empty = evidence(audit_module, pip_raw="", pip_exit=1)
    assert invalid["execution_state"] == audit_module.OPERATIONAL_FAILURE
    assert empty["execution_state"] == audit_module.OPERATIONAL_FAILURE


def test_summary_separates_execution_findings_and_gate(audit_module):
    result = evidence(audit_module, pip_raw=pip_payload())
    summary = audit_module.render_summary(result)
    assert "## Validade da execução" in summary
    assert "## Achados" in summary
    assert "## Decisão de gate" in summary


def test_workflow_preserves_raw_evidence_routes_and_fails_closed():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "timeout 180" in workflow
    assert "pip-audit.metadata.json" in workflow
    assert "npm-audit.metadata.json" in workflow
    assert "dependency-audit-evidence" in workflow
    assert "operational-failures.json" in workflow
    assert "dependency-audit-fingerprint" in workflow
    assert "FAIL_CLOSED_OPERATIONAL_FAILURE" in workflow
    assert "|| true" not in workflow


def test_aliases_merge_patch_evidence_independent_of_order(audit_module):
    records = [
        {"id": "PYSEC-2026-1", "aliases": ["CVE-2026-12345"], "fix_versions": []},
        {"id": "GHSA-abcd-1234-5678", "aliases": ["CVE-2026-12345"], "fix_versions": ["69.0"]},
    ]
    forward = evidence(audit_module, pip_raw=pip_payload(*records), pip_exit=1)
    backward = evidence(audit_module, pip_raw=pip_payload(*reversed(records)), pip_exit=1)
    assert forward == backward
    assert forward["counts"]["total"] == 1
    assert forward["counts"]["fixable"] == 1
    assert forward["findings"][0]["vulnerability_id"] == "CVE-2026-12345"
    assert "PYSEC-2026-1" in forward["findings"][0]["aliases"]


def test_same_advisory_keeps_distinct_packages_and_versions(audit_module):
    record = {"id": "CVE-2026-12345", "aliases": [], "fix_versions": []}
    payload = {"dependencies": [
        {"name": name, "version": version, "vulns": [record]}
        for name, version in [("one", "1.0"), ("one", "2.0"), ("two", "1.0")]
    ]}
    result = evidence(audit_module, pip_raw=payload, pip_exit=1)
    assert result["counts"]["total"] == 3


def test_npm_lock_versions_are_not_advisory_ranges(audit_module):
    import json

    payload = npm_payload(vulnerabilities={
        "parent": {"via": ["child"], "range": "*", "nodes": ["node_modules/parent"], "fixAvailable": True},
        "child": {"via": [{"url": "https://github.com/advisories/GHSA-abcd-1234-5678", "range": "<2.0"}],
                  "range": "<2.0", "nodes": ["node_modules/child", "node_modules/parent/node_modules/child"], "fixAvailable": True},
    })
    lock = {"packages": {
        "node_modules/parent": {"version": "3.0"},
        "node_modules/child": {"version": "1.1"},
        "node_modules/parent/node_modules/child": {"version": "1.2"},
    }}
    result = audit_module.analyze_scanner("npm-audit", json.dumps(payload), {"exit_code": 1}, lock)
    assert len(result.findings) == 1
    assert result.findings[0].installed_version == "1.1, 1.2"
    assert result.findings[0].affected_range == "<2.0"
    assert result.findings[0].vulnerability_id == "GHSA-abcd-1234-5678"
    invalid = audit_module.analyze_scanner("npm-audit", json.dumps(payload), {"exit_code": 1}, {"packages": {}})
    assert invalid.state == audit_module.OPERATIONAL_FAILURE


def test_npm_missing_advisory_cannot_become_clean_scan(audit_module):
    import json

    payload = npm_payload(vulnerabilities={"parent": {"via": ["missing"], "fixAvailable": False}})
    result = audit_module.analyze_scanner("npm-audit", json.dumps(payload), {"exit_code": 1})
    assert result.state == audit_module.OPERATIONAL_FAILURE


def test_exit_one_without_findings_is_not_a_clean_scan(audit_module):
    result = evidence(audit_module, pip_raw=pip_payload(), pip_exit=1)
    assert result["execution_state"] == audit_module.OPERATIONAL_FAILURE
