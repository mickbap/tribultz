"""ERPConnectorTool – import invoices from CSV and NF-e XML."""

import csv
import io
import logging
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────
class ImportedItem(BaseModel):
    sku: str = ""
    description: str = ""
    ncm_code: str = ""
    quantity: Decimal = Decimal("1")
    unit_price: Decimal = Decimal("0")
    total_price: Decimal = Decimal("0")


class ImportedInvoice(BaseModel):
    source: str                   # "csv" | "xml_nfe"
    invoice_number: str
    issue_date: Optional[date] = None
    cnpj_emitter: str = ""
    cnpj_recipient: str = ""
    total_amount: Decimal = Decimal("0")
    items: list[ImportedItem] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


# ── 1. Import CSV Invoices ────────────────────────────────────
def import_csv_invoices(csv_bytes: bytes, encoding: str = "utf-8") -> list[dict]:
    """
    Parse a CSV file with columns:
      invoice_number, issue_date, cnpj_emitter, cnpj_recipient,
      sku, description, ncm_code, quantity, unit_price, total_price

    Groups rows by invoice_number and returns a list of ImportedInvoice dicts.
    """
    text_io = io.StringIO(csv_bytes.decode(encoding))
    reader = csv.DictReader(text_io, delimiter=";")

    invoices: dict[str, ImportedInvoice] = {}

    for row in reader:
        inv_num = row.get("invoice_number", "").strip()
        if not inv_num:
            continue

        if inv_num not in invoices:
            invoices[inv_num] = ImportedInvoice(
                source="csv",
                invoice_number=inv_num,
                issue_date=_parse_date(row.get("issue_date", "")),
                cnpj_emitter=row.get("cnpj_emitter", "").strip(),
                cnpj_recipient=row.get("cnpj_recipient", "").strip(),
            )

        item = ImportedItem(
            sku=row.get("sku", "").strip(),
            description=row.get("description", "").strip(),
            ncm_code=row.get("ncm_code", "").strip(),
            quantity=Decimal(row.get("quantity", "1") or "1"),
            unit_price=Decimal(row.get("unit_price", "0") or "0"),
            total_price=Decimal(row.get("total_price", "0") or "0"),
        )
        invoices[inv_num].items.append(item)

    # Sum totals
    for inv in invoices.values():
        inv.total_amount = sum(it.total_price for it in inv.items)

    result = [inv.model_dump(mode="json") for inv in invoices.values()]
    logger.info("import_csv_invoices: parsed %d invoices", len(result))
    return result


# ── 2. Import XML NF-e ────────────────────────────────────────
NFE_NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


def import_xml_nfe(xml_bytes: bytes) -> dict:
    """
    Parse a Brazilian NF-e XML and return an ImportedInvoice dict.
    This is an initial implementation that handles the standard
    NF-e 4.00 layout.  Fields not found are returned as empty strings.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("XML parse failed, returning stub: %s", exc)
        return _nfe_stub(str(exc))

    # Try with namespace first, then without
    ide = root.find(".//nfe:ide", NFE_NS) or root.find(".//ide")
    emit = root.find(".//nfe:emit", NFE_NS) or root.find(".//emit")
    dest = root.find(".//nfe:dest", NFE_NS) or root.find(".//dest")
    det_list = root.findall(".//nfe:det", NFE_NS) or root.findall(".//det")
    total_el = (
        root.find(".//nfe:ICMSTot/nfe:vNF", NFE_NS)
        or root.find(".//ICMSTot/vNF")
    )

    inv = ImportedInvoice(
        source="xml_nfe",
        invoice_number=_text(ide, "nNF") if ide is not None else "",
        issue_date=_parse_date(_text(ide, "dhEmi")[:10] if ide is not None else ""),
        cnpj_emitter=_text(emit, "CNPJ") if emit is not None else "",
        cnpj_recipient=_text(dest, "CNPJ") if dest is not None else "",
        total_amount=Decimal(total_el.text) if total_el is not None and total_el.text else Decimal("0"),
    )

    for det in det_list:
        prod = det.find("nfe:prod", NFE_NS) or det.find("prod")
        if prod is None:
            continue
        inv.items.append(ImportedItem(
            sku=_text(prod, "cProd"),
            description=_text(prod, "xProd"),
            ncm_code=_text(prod, "NCM"),
            quantity=Decimal(_text(prod, "qCom") or "1"),
            unit_price=Decimal(_text(prod, "vUnCom") or "0"),
            total_price=Decimal(_text(prod, "vProd") or "0"),
        ))

    logger.info("import_xml_nfe: parsed invoice %s with %d items", inv.invoice_number, len(inv.items))
    return inv.model_dump(mode="json")


# ── Helpers ───────────────────────────────────────────────────
def _text(parent, tag: str) -> str:
    """Extract text from a child element, namespace-aware."""
    if parent is None:
        return ""
    el = parent.find(f"nfe:{tag}", NFE_NS) or parent.find(tag)
    return (el.text or "").strip() if el is not None else ""


def _parse_date(raw: str) -> Optional[date]:
    raw = raw.strip()[:10]
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _nfe_stub(error: str) -> dict:
    """Fallback stub when XML parsing fails."""
    return ImportedInvoice(
        source="xml_nfe",
        invoice_number="PARSE_ERROR",
        raw_metadata={"parse_error": error},
    ).model_dump(mode="json")
