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


def correct_xml(
    *,
    xml: str,
    document_type: str | None,
    findings: list[dict] | None = None,
) -> tuple[str, CorrectionSummary]:
    """Return (corrected_xml, summary).

    MVP strategy: normalize only and mark all incoming findings as unresolved.
    """
    normalized = _normalize_xml(xml)
    summary = CorrectionSummary(
        applied_corrections=[
            "whitespace_normalization",
        ],
        unresolved_findings=[f for f in findings or []],
    )
    return normalized, summary
