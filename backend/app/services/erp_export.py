"""ERP Export Service — gera CSV/TXT por ERP a partir do catálogo SPED validado.

Formatos suportados:
  totvs   — CSV `;` latin-1  (TOTVS Protheus)
  sap     — CSV `,` UTF-8   (SAP Business One)
  omie    — CSV `,` UTF-8   (Omie)
  linx    — TXT posicional  latin-1  (Linx)
  generic — CSV `;` UTF-8   (genérico ERP)
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Literal

ErpFormat = Literal["totvs", "sap", "omie", "linx", "generic"]

_TOTVS_HEADERS = [
    "CODIGOPROD", "DESCRICAO", "NCM", "CEST", "CLASSTRIB",
    "CSTCBS", "CSTIBS", "ALIQCBS", "ALIQIBS",
    "STATUS", "SEVERIDADE", "DTVALIDACAO",
]
_SAP_HEADERS = [
    "ItemCode", "ItemName", "NCMCode", "CESTCode", "ClassTrib",
    "CSTCBS", "CSTIBS", "CBSRate", "IBSRate",
    "ValidationStatus", "FindingSeverity", "ValidationDate",
]
_OMIE_HEADERS = [
    "codigo", "descricao", "ncm", "cest", "cClassTrib",
    "cst_cbs", "cst_ibs", "aliquota_cbs", "aliquota_ibs",
    "status_validacao", "severidade", "data_validacao",
]

# Widths for Linx positional format (total = 131 chars per line)
_LINX_FIELDS: list[tuple[str, int]] = [
    ("codigo_produto",   20),
    ("descricao",        60),
    ("ncm",               8),
    ("cest",              7),
    ("aliquota_cbs",      8),
    ("aliquota_ibs",      8),
    ("status_validacao", 10),
    ("data_validacao",   10),
]


def _normalize(p: dict, today: str) -> dict:
    flags = p.get("flags", [])
    return {
        "codigo_produto":    p.get("cod_item", ""),
        "descricao":         p.get("descr", ""),
        "ncm":               p.get("ncm", ""),
        "cest":              p.get("cest", ""),
        "cClassTrib":        p.get("cClassTrib", ""),
        "cst_cbs":           p.get("cst_cbs", ""),
        "cst_ibs":           p.get("cst_ibs", ""),
        "aliquota_cbs":      p.get("cbs_rate", ""),
        "aliquota_ibs":      p.get("ibs_rate", ""),
        "status_validacao":  p.get("status", ""),
        "finding_severity":  "ERROR" if flags else "OK",
        "data_validacao":    today,
    }


def _csv_bytes(rows: list[dict], delimiter: str, headers: list[str], encoding: str) -> bytes:
    keys = [
        "codigo_produto", "descricao", "ncm", "cest", "cClassTrib",
        "cst_cbs", "cst_ibs", "aliquota_cbs", "aliquota_ibs",
        "status_validacao", "finding_severity", "data_validacao",
    ]
    buf = io.StringIO()
    buf.write(delimiter.join(headers) + "\r\n")
    writer = csv.DictWriter(buf, fieldnames=keys, delimiter=delimiter, extrasaction="ignore")
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode(encoding, errors="replace")


def _linx_bytes(rows: list[dict], encoding: str) -> bytes:
    lines: list[str] = []
    for r in rows:
        line = "".join(r.get(field, "").ljust(width)[:width] for field, width in _LINX_FIELDS)
        lines.append(line)
    return "\r\n".join(lines).encode(encoding, errors="replace")


def generate(
    produtos: list[dict],
    fmt: ErpFormat,
    data_validacao: str | None = None,
) -> tuple[bytes, str, str]:
    """Return ``(content_bytes, content_type, filename_suffix)``."""
    today = data_validacao or date.today().isoformat()
    rows = [_normalize(p, today) for p in produtos]

    if fmt == "totvs":
        return _csv_bytes(rows, ";", _TOTVS_HEADERS, "latin-1"), "text/csv; charset=iso-8859-1", "totvs.csv"
    if fmt == "sap":
        return _csv_bytes(rows, ",", _SAP_HEADERS, "utf-8"), "text/csv; charset=utf-8", "sap.csv"
    if fmt == "omie":
        return _csv_bytes(rows, ",", _OMIE_HEADERS, "utf-8"), "text/csv; charset=utf-8", "omie.csv"
    if fmt == "linx":
        return _linx_bytes(rows, "latin-1"), "text/plain; charset=iso-8859-1", "linx.txt"
    # generic
    return _csv_bytes(rows, ";", _TOTVS_HEADERS, "utf-8"), "text/csv; charset=utf-8", "generico.csv"
