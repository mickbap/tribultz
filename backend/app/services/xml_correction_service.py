"""Deterministic XML correction service (MVP).

For now, this performs conservative, non-destructive normalization only:
- Preserves structure and content
- Normalizes whitespace and line endings

Future iterations can apply safe rule-driven fixes when we have
authoritative data sources (e.g., padding numeric formats, recalculating
totals when all operands are present, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Optional


@dataclass
class CorrectionSummary:
    applied_corrections: list[str]
    unresolved_findings: list[dict]


def _normalize_xml(xml: str) -> str:
    """Pretty-print without altering tag/attribute ordering too aggressively.

    Uses ElementTree to reserialize. If parsing fails, returns original.
    """
    try:
        # Parse and re-serialize to normalize whitespace/newlines
        root = ET.fromstring(xml)
        # Minimal pretty print: join all text/tails trimmed
        def _recurse(node: ET.Element) -> None:
            if node.text:
                node.text = node.text.strip()
            for child in list(node):
                _recurse(child)
            if node.tail:
                node.tail = node.tail.strip()
        _recurse(root)
        return ET.tostring(root, encoding="utf-8").decode("utf-8")
    except Exception:
        return xml


def _localname(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _find_first(root: ET.Element, name: str) -> Optional[ET.Element]:
    for el in root.iter():
        if _localname(el.tag) == name:
            return el
    return None


def _to_float(s: Optional[str]) -> Optional[float]:
    if s is None:
        return None
    try:
        return float(str(s).strip().replace(",", "."))
    except Exception:
        return None


def _fmt2(v: float) -> str:
    return f"{round(v + 1e-12, 2):.2f}"


def _recalc_taxes(root: ET.Element) -> list[str]:
    """Deterministically recalc supported tax fields when operands exist.

    Overwrites only existing value tags (non-structural). Returns flags.
    """
    applied: list[str] = []

    # NF-e style — IBSCBS group values
    vbc_el = _find_first(root, "vBC")
    pcbs_el = _find_first(root, "pCBS")
    vcbs_el = _find_first(root, "vCBS")
    pibsuf_el = _find_first(root, "pIBSUF")
    vibsuf_el = _find_first(root, "vIBSUF")
    pibsm_el = _find_first(root, "pIBSMun")
    vibsm_el = _find_first(root, "vIBSMun")
    vibs_el = _find_first(root, "vIBS")

    base = _to_float(vbc_el.text if vbc_el is not None else None)
    if base is not None and pcbs_el is not None and vcbs_el is not None:
        r = _to_float(pcbs_el.text)
        if r is not None:
            vcbs_el.text = _fmt2(base * r)
            applied.append("recalc_vCBS")
    if base is not None and pibsuf_el is not None and vibsuf_el is not None:
        r = _to_float(pibsuf_el.text)
        if r is not None:
            vibsuf_el.text = _fmt2(base * r)
            applied.append("recalc_vIBSUF")
    if base is not None and pibsm_el is not None and vibsm_el is not None:
        r = _to_float(pibsm_el.text)
        if r is not None:
            vibsm_el.text = _fmt2(base * r)
            applied.append("recalc_vIBSMun")
    if vibs_el is not None and vibsuf_el is not None and vibsm_el is not None:
        uf = _to_float(vibsuf_el.text)
        mn = _to_float(vibsm_el.text)
        if uf is not None and mn is not None:
            vibs_el.text = _fmt2(uf + mn)
            applied.append("recalc_vIBS")

    # NFS-e legacy style — ValorCBS/ValorIBS
    base_nfse_el = _find_first(root, "BaseCalculo") or _find_first(root, "vBC")
    aliq_cbs_el = _find_first(root, "AliquotaCBS") or _find_first(root, "pCBS")
    aliq_ibs_el = _find_first(root, "AliquotaIBS")
    valor_cbs_el = _find_first(root, "ValorCBS") or (vcbs_el if _find_first(root, "IBSCBS") is None else None)
    valor_ibs_el = _find_first(root, "ValorIBS") or (vibs_el if _find_first(root, "IBSCBS") is None else None)

    base_nfse = _to_float(base_nfse_el.text if base_nfse_el is not None else None)
    if base_nfse is not None and aliq_cbs_el is not None and valor_cbs_el is not None:
        r = _to_float(aliq_cbs_el.text)
        if r is not None:
            valor_cbs_el.text = _fmt2(base_nfse * r)
            applied.append("recalc_ValorCBS")
    if base_nfse is not None and aliq_ibs_el is not None and valor_ibs_el is not None:
        r = _to_float(aliq_ibs_el.text)
        if r is not None:
            valor_ibs_el.text = _fmt2(base_nfse * r)
            applied.append("recalc_ValorIBS")

    return applied


def correct_xml(
    *,
    xml: str,
    document_type: str | None,
    findings: list[dict] | None = None,
) -> tuple[str, CorrectionSummary]:
    """Return (corrected_xml, summary).

    MVP strategy: normalize only and mark all incoming findings as unresolved.
    """
    applied: list[str] = []
    corrected = xml
    try:
        root = ET.fromstring(xml)
        applied += _recalc_taxes(root)
        corrected = ET.tostring(root, encoding="utf-8").decode("utf-8")
    except Exception:
        corrected = xml
    normalized = _normalize_xml(corrected)
    summary = CorrectionSummary(
        applied_corrections=(applied + ["whitespace_normalization"]),
        unresolved_findings=[f for f in (findings or [])],
    )
    return normalized, summary
