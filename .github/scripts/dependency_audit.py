#!/usr/bin/env python3
"""Validate dependency scanner evidence without turning failures into zero findings."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Any


VALID_NO_FINDINGS = "SCAN_VALID_NO_FINDINGS"
VALID_WITH_FINDINGS = "SCAN_VALID_WITH_FINDINGS"
OPERATIONAL_FAILURE = "SCAN_OPERATIONAL_FAILURE"
EXPECTED_EXIT_CODES = {0, 1}


class InvalidScannerEvidence(ValueError):
    pass


@dataclass(frozen=True)
class Finding:
    scanner: str
    package: str
    installed_version: str
    vulnerability_id: str
    aliases: tuple[str, ...]
    severity: str
    fix_status: str
    fix_versions: tuple[str, ...]
    fingerprint: str
    affected_range: str | None = None


@dataclass(frozen=True)
class ScannerResult:
    scanner: str
    state: str
    exit_code: int
    findings: tuple[Finding, ...]
    operational_failures: tuple[str, ...]


def _fingerprint(scanner: str, package: str, vulnerability_id: str) -> str:
    material = f"{scanner}|{package.lower()}|{vulnerability_id.lower()}"
    return hashlib.sha256(material.encode()).hexdigest()[:20]


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvalidScannerEvidence(f"{label}: objeto JSON esperado")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise InvalidScannerEvidence(f"{label}: lista JSON esperada")
    return value


def parse_pip_audit(data: Any) -> list[Finding]:
    root = _require_dict(data, "pip-audit")
    dependencies = _require_list(root.get("dependencies"), "pip-audit.dependencies")
    findings: list[Finding] = []
    for dep_index, raw_dep in enumerate(dependencies):
        dep = _require_dict(raw_dep, f"pip-audit.dependencies[{dep_index}]")
        name = dep.get("name")
        version = dep.get("version")
        vulns = _require_list(dep.get("vulns"), f"pip-audit.dependencies[{dep_index}].vulns")
        if not isinstance(name, str) or not isinstance(version, str):
            raise InvalidScannerEvidence("pip-audit: dependência sem name/version válidos")
        for vuln_index, raw_vuln in enumerate(vulns):
            vuln = _require_dict(raw_vuln, f"pip-audit.vulns[{vuln_index}]")
            vuln_id = vuln.get("id")
            fix_versions = vuln.get("fix_versions", [])
            aliases = vuln.get("aliases", [])
            if not isinstance(vuln_id, str):
                raise InvalidScannerEvidence("pip-audit: vulnerabilidade sem id")
            if not isinstance(fix_versions, list) or not all(
                isinstance(item, str) for item in fix_versions
            ):
                raise InvalidScannerEvidence("pip-audit: fix_versions inválido")
            if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
                raise InvalidScannerEvidence("pip-audit: aliases inválido")
            findings.append(
                Finding(
                    scanner="pip-audit",
                    package=name,
                    installed_version=version,
                    vulnerability_id=vuln_id,
                    aliases=tuple(sorted(set(aliases))),
                    severity=str(vuln.get("severity") or "unknown").lower(),
                    fix_status="FIXABLE" if fix_versions else "NO_PATCH_DECLARED",
                    fix_versions=tuple(sorted(set(fix_versions))),
                    fingerprint=_fingerprint("pip-audit", name, vuln_id),
                )
            )
    return findings


def _npm_fix(raw_fix: Any) -> tuple[str, tuple[str, ...]]:
    if raw_fix is True:
        return "FIXABLE", ()
    if isinstance(raw_fix, dict):
        name = raw_fix.get("name")
        version = raw_fix.get("version")
        target = f"{name}@{version}" if isinstance(name, str) and isinstance(version, str) else ""
        return "FIXABLE", (target,) if target else ()
    if raw_fix is False:
        return "NO_PATCH_DECLARED", ()
    return "FIX_STATUS_UNKNOWN", ()


def parse_npm_audit(data: Any, lockfile: Any = None) -> list[Finding]:
    root = _require_dict(data, "npm-audit")
    vulnerabilities = _require_dict(root.get("vulnerabilities"), "npm-audit.vulnerabilities")
    _require_dict(root.get("metadata"), "npm-audit.metadata")
    packages = (
        _require_dict(_require_dict(lockfile, "npm-lock").get("packages"), "npm-lock.packages")
        if lockfile is not None else {}
    )
    findings: list[Finding] = []
    for package, raw_vuln in vulnerabilities.items():
        vuln = _require_dict(raw_vuln, f"npm-audit.vulnerabilities.{package}")
        severity = str(vuln.get("severity") or "unknown").lower()
        fix_status, fix_versions = _npm_fix(vuln.get("fixAvailable"))
        via = _require_list(vuln.get("via"), f"npm-audit.vulnerabilities.{package}.via")
        nodes = _require_list(vuln.get("nodes", []), f"npm-audit.{package}.nodes")
        versions: set[str] = set()
        for node in nodes:
            if not isinstance(node, str):
                raise InvalidScannerEvidence("npm-audit: node inválido")
            entry = packages.get(node)
            if lockfile is not None:
                entry = _require_dict(entry, f"npm-lock.{node}")
                version = entry.get("version")
                if not isinstance(version, str):
                    raise InvalidScannerEvidence(f"npm-lock: versão ausente para {node}")
                versions.add(version)
        if lockfile is not None and not versions:
            raise InvalidScannerEvidence(f"npm-audit: nodes ausentes para {package}")
        for item in via:
            if isinstance(item, str):
                # A package edge is not a separate advisory. The dependency has
                # its own entry with the concrete advisory and affected nodes.
                if item not in vulnerabilities:
                    raise InvalidScannerEvidence(f"npm-audit: dependência via ausente ({item})")
                continue
            item = _require_dict(item, f"npm-audit.{package}.via")
            advisory_id = item.get("url") or item.get("source") or item.get("title")
            if advisory_id is None:
                raise InvalidScannerEvidence(f"npm-audit: advisory sem identificador ({package})")
            advisory_id = str(advisory_id)
            if advisory_id.startswith("https://github.com/advisories/"):
                advisory_id = advisory_id.rsplit("/", 1)[-1]
            findings.append(Finding(
                scanner="npm-audit", package=package,
                installed_version=", ".join(sorted(versions)) or "unknown",
                vulnerability_id=advisory_id, aliases=(),
                severity=str(item.get("severity") or severity).lower(),
                fix_status=fix_status, fix_versions=fix_versions,
                fingerprint=_fingerprint("npm-audit", package, advisory_id),
                affected_range=str(item.get("range") or vuln.get("range") or "unknown"),
            ))
    if vulnerabilities and not findings:
        raise InvalidScannerEvidence("npm-audit: vulnerabilidades sem advisory concreto")
    return findings


def deduplicate(findings: list[Finding]) -> tuple[Finding, ...]:
    """Merge connected alias sets, retaining package/version boundaries and patches."""
    groups: list[tuple[list[Finding], set[str]]] = []
    for finding in findings:
        ids = {finding.vulnerability_id, *finding.aliases}
        members = [finding]
        remaining = []
        for existing, existing_ids in groups:
            first = existing[0]
            same_dependency = (
                first.scanner, first.package.lower(), first.installed_version
            ) == (finding.scanner, finding.package.lower(), finding.installed_version)
            if same_dependency and ids & existing_ids:
                members.extend(existing)
                ids.update(existing_ids)
            else:
                remaining.append((existing, existing_ids))
        # Existing groups are disjoint; all overlaps with this record now merge.
        groups = [*remaining, (members, ids)]
    normalized = []
    ranks = {"unknown": 0, "info": 1, "low": 2, "moderate": 3, "medium": 3, "high": 4, "critical": 5}
    for members, ids in groups:
        canonical = min(ids, key=lambda value: (
            0 if value.startswith("CVE-") else 1 if value.startswith("GHSA-") else 2, value
        ))
        first = members[0]
        fixes = tuple(sorted({version for item in members for version in item.fix_versions}))
        normalized.append(replace(
            first, vulnerability_id=canonical, aliases=tuple(sorted(ids - {canonical})),
            severity=max((item.severity for item in members), key=lambda value: (ranks.get(value, 0), value)),
            fix_status="FIXABLE" if any(item.fix_status == "FIXABLE" for item in members) else first.fix_status,
            fix_versions=fixes,
            fingerprint=_fingerprint(first.scanner, first.package, canonical),
        ))
    return tuple(sorted(normalized, key=lambda item: (item.fingerprint, item.installed_version)))


def analyze_scanner(
    scanner: str, raw_text: str, metadata: dict[str, Any], npm_lock: Any = None,
) -> ScannerResult:
    exit_code = metadata.get("exit_code")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        return ScannerResult(scanner, OPERATIONAL_FAILURE, -1, (), ("exit_code ausente/inválido",))
    failures: list[str] = []
    if metadata.get("timed_out") is True or exit_code in (124, 137):
        failures.append("scanner excedeu timeout")
    elif exit_code not in EXPECTED_EXIT_CODES:
        failures.append(f"exit inesperado: {exit_code}")
    if not raw_text.strip():
        failures.append("saída JSON vazia")
        data: Any = None
    else:
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            failures.append(f"JSON inválido: {exc.msg}")
            data = None

    findings: list[Finding] = []
    if data is not None:
        try:
            findings = parse_pip_audit(data) if scanner == "pip-audit" else parse_npm_audit(data, npm_lock)
        except InvalidScannerEvidence as exc:
            failures.append(f"schema inválido: {exc}")

    if failures:
        return ScannerResult(scanner, OPERATIONAL_FAILURE, exit_code, (), tuple(failures))
    normalized = deduplicate(findings)
    if exit_code == 1 and not normalized:
        return ScannerResult(scanner, OPERATIONAL_FAILURE, exit_code, (), ("exit 1 sem achados verificáveis",))
    state = VALID_WITH_FINDINGS if normalized else VALID_NO_FINDINGS
    return ScannerResult(scanner, state, exit_code, normalized, ())


def analyze(evidence: dict[str, tuple[str, dict[str, Any]]], npm_lock: Any = None) -> dict[str, Any]:
    scanner_results = [
        analyze_scanner(scanner, raw_text, metadata, npm_lock)
        for scanner, (raw_text, metadata) in sorted(evidence.items())
    ]
    unique_findings = {
        (finding.fingerprint, finding.installed_version): finding
        for result in scanner_results
        for finding in result.findings
    }
    findings = sorted(unique_findings.values(), key=lambda item: item.fingerprint)
    failures = [
        {"scanner": result.scanner, "reasons": list(result.operational_failures)}
        for result in scanner_results
        if result.operational_failures
    ]
    if failures:
        state = OPERATIONAL_FAILURE
        gate = "FAIL_CLOSED_OPERATIONAL_FAILURE"
    elif findings:
        state = VALID_WITH_FINDINGS
        gate = "PASS_WITH_FINDINGS_ROUTED"
    else:
        state = VALID_NO_FINDINGS
        gate = "PASS_NO_FINDINGS"
    fixable = [finding for finding in findings if finding.fix_status == "FIXABLE"]
    no_patch = [finding for finding in findings if finding.fix_status != "FIXABLE"]
    return {
        "execution_state": state,
        "gate_decision": gate,
        "scanner_results": [
            {
                "scanner": result.scanner,
                "state": result.state,
                "exit_code": result.exit_code,
                "finding_count": len(result.findings),
                "operational_failures": list(result.operational_failures),
            }
            for result in scanner_results
        ],
        "findings": [asdict(finding) for finding in findings],
        "operational_failures": failures,
        "counts": {
            "total": len(findings),
            "fixable": len(fixable),
            "no_patch_declared_or_unknown": len(no_patch),
            "operational_failures": len(failures),
        },
    }


def render_summary(result: dict[str, Any]) -> str:
    counts = result["counts"]
    lines = [
        "# Relatório de Auditoria de Dependências",
        "",
        "## Validade da execução",
        "",
        f"- Estado: **{result['execution_state']}**",
    ]
    for scanner in result["scanner_results"]:
        lines.append(
            f"- {scanner['scanner']}: {scanner['state']} "
            f"(exit={scanner['exit_code']}, achados={scanner['finding_count']})"
        )
    lines.extend(
        [
            "",
            "## Achados",
            "",
            f"- Total deduplicado: **{counts['total']}**",
            f"- Corrigíveis segundo o scanner: **{counts['fixable']}**",
            "- Sem patch declarado ou com status ainda não verificado: "
            f"**{counts['no_patch_declared_or_unknown']}**",
            "",
            "A ausência de versão de correção no scanner não prova que upstream não possua correção.",
            "",
            "## Decisão de gate",
            "",
            f"**{result['gate_decision']}**",
        ]
    )
    if result["operational_failures"]:
        lines.extend(["", "## Exceções operacionais (separadas dos achados)", ""])
        for failure in result["operational_failures"]:
            lines.append(f"- {failure['scanner']}: {', '.join(failure['reasons'])}")
    return "\n".join(lines) + "\n"


def render_findings(findings: list[dict[str, Any]], *, fixable: bool) -> str:
    selected = [item for item in findings if (item["fix_status"] == "FIXABLE") is fixable]
    lines: list[str] = []
    for item in selected:
        fix_versions = ", ".join(item["fix_versions"]) or "versão não informada"
        qualifier = (
            f"correção declarada: {fix_versions}"
            if fixable
            else "scanner não declarou patch; verificar advisory/upstream"
        )
        aliases = ", ".join(item["aliases"])
        alias_text = f"; aliases: {aliases}" if aliases else ""
        affected = item.get("affected_range")
        range_text = f"; faixa afetada: {affected}" if affected else ""
        lines.append(
            f"- `{item['package']} {item['installed_version']}` — "
            f"{item['vulnerability_id']} ({item['scanner']}, {item['severity']}) — "
            f"{qualifier}{alias_text}{range_text} — fingerprint `{item['fingerprint']}`"
        )
    return "\n".join(lines) + ("\n" if lines else "")


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        return _require_dict(json.loads(path.read_text(encoding="utf-8")), path.name)
    except (OSError, json.JSONDecodeError, InvalidScannerEvidence) as exc:
        return {"exit_code": -1, "metadata_error": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    evidence: dict[str, tuple[str, dict[str, Any]]] = {}
    for scanner, stem in (("pip-audit", "pip-audit"), ("npm-audit", "npm-audit")):
        raw_path = args.evidence_dir / f"{stem}.json"
        metadata_path = args.evidence_dir / f"{stem}.metadata.json"
        try:
            raw = raw_path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        evidence[scanner] = (raw, _read_metadata(metadata_path))

    try:
        npm_lock = json.loads((args.evidence_dir / "npm-lock.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        npm_lock = {}  # Missing lockfile is an operational failure, never an invented version.
    result = analyze(evidence, npm_lock)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "summary.md").write_text(render_summary(result), encoding="utf-8")
    (args.output_dir / "fixable.md").write_text(
        render_findings(result["findings"], fixable=True), encoding="utf-8"
    )
    (args.output_dir / "no-patch.md").write_text(
        render_findings(result["findings"], fixable=False), encoding="utf-8"
    )
    (args.output_dir / "operational-failures.json").write_text(
        json.dumps(result["operational_failures"], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"execution_state": result["execution_state"], "counts": result["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
