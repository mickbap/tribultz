from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.s3_tool import put_object

# CST table from NT 2025.002-RTC
CST_TABLE: dict[str, dict[str, str | None]] = {
    "000": {"group": "gIBSCBS", "description": "Tributacao normal (ad valorem)"},
    "001": {"group": "gIBSCBS", "description": "Tributacao normal com reducao de base"},
    "002": {"group": "gIBSCBSMono", "description": "Tributacao ad rem"},
    "070": {"group": None, "description": "Imunidade / Isencao"},
    "200": {"group": "gIBSCBS", "description": "Diferimento"},
    "410": {"group": None, "description": "Suspensao"},
    "510": {"group": "gIBSCBS", "description": "Credito presumido"},
    "515": {"group": "gIBSCBS", "description": "Credito presumido especial"},
    "550": {"group": "gIBSCBS", "description": "Regime especifico"},
    "620": {"group": "gIBSCBSMono", "description": "Monofasico"},
    "800": {"group": "gTransfCred", "description": "Transferencia de credito"},
    "810": {"group": None, "description": "Ressarcimento"},
    "811": {"group": "gAjusteCompet", "description": "Ajuste de competencia"},
    "830": {"group": "gEstornoCred", "description": "Estorno de credito"},
}


class ParseNFeInput(BaseModel):
    xml_content: str = Field(
        description="NF-e or NFC-e XML string to parse. Paste the full XML content."
    )


class ParseNFeXMLTool(BaseTool):
    """
    Parse a NF-e/NFC-e XML string (NT 2025.002-RTC), store raw XML in S3,
    and extract IBSCBS fiscal fields including IBS UF/Municipal split.
    tenant_id is injected at construction and never exposed to the LLM.
    """

    name: str = "parse_nfe_xml"
    description: str = (
        "Parse a NF-e or NFC-e XML string with IBSCBS group (NT 2025.002-RTC). "
        "Extracts: CST, cClassTrib, NCM, CEST, vBC, pCBS, vCBS, pIBSUF, vIBSUF, "
        "pIBSMun, vIBSMun, vIBS, IBSCBSTot totals, and document type (mod 55/65). "
        "Stores original XML in S3. "
        "Returns JSON with {invoice_id, s3_key, doc_type, parse_error, fields, items[]}."
    )
    args_schema: Type[BaseModel] = ParseNFeInput
    tenant_id: str  # injected at construction — never exposed to LLM
    transaction_id: str | None = None

    def _run(self, xml_content: str) -> str:
        invoice_id = str(uuid.uuid4())
        s3_key = f"invoices/{self.tenant_id}/{invoice_id}.xml"

        # Store raw XML — soft-fail if S3 unavailable (local dev)
        try:
            put_object(
                key=s3_key,
                data=xml_content.encode("utf-8"),
                content_type="application/xml",
                metadata={"tenant_id": self.tenant_id, "invoice_id": invoice_id},
                transaction_id=self.transaction_id,
            )
        except Exception as exc:
            s3_key = f"(s3-unavailable: {exc})"

        # Detect document type from mod tag
        doc_type = "NFE"
        mod_match = re.search(r"<mod>\s*(\d+)\s*</mod>", xml_content, re.IGNORECASE)
        if mod_match:
            if mod_match.group(1) == "65":
                doc_type = "NFCE"

        # Global fields
        fields: dict[str, str] = {
            "cst": "",
            "cclasstrib": "",
            "ncm": "",
            "cest": "",
            "vbc": "",
            "pcbs": "",
            "vcbs": "",
            "pibsuf": "",
            "vibsuf": "",
            "pibsmun": "",
            "vibsmun": "",
            "vibs": "",
            # Totals from IBSCBSTot
            "tot_vcbs": "",
            "tot_vibs": "",
        }
        parse_error: str | None = None

        # Per-item extraction (NF-e can have multiple <det> items)
        items: list[dict[str, str]] = []

        # Track NF-e layout tags
        layout_tags: dict[str, bool] = {
            "emit": False,
            "det": False,
            "total": False,
            "IBSCBS": False,
            "IBSCBSTot": False,
        }

        try:
            root = ET.fromstring(xml_content.strip())

            # Find parent context for IBSCBS CST extraction
            ibscbs_cst_found = False

            for elem in root.iter():
                tag = elem.tag.split("}")[-1]
                text = (elem.text or "").strip()

                if tag in layout_tags:
                    layout_tags[tag] = True

                # Extract per-item fields from inside IBSCBS groups
                if tag == "IBSCBS":
                    item: dict[str, str] = {}
                    for child in elem.iter():
                        ctag = child.tag.split("}")[-1]
                        ctext = (child.text or "").strip()
                        if ctag == "CST":
                            item["cst"] = ctext
                            if not ibscbs_cst_found:
                                fields["cst"] = ctext
                                ibscbs_cst_found = True
                        elif ctag == "cClassTrib":
                            item["cclasstrib"] = ctext
                            if not fields["cclasstrib"]:
                                fields["cclasstrib"] = ctext
                        elif ctag == "vBC":
                            item["vbc"] = ctext
                            if not fields["vbc"]:
                                fields["vbc"] = ctext
                        elif ctag == "pCBS":
                            item["pcbs"] = ctext
                            if not fields["pcbs"]:
                                fields["pcbs"] = ctext
                        elif ctag == "vCBS":
                            item["vcbs"] = ctext
                            if not fields["vcbs"]:
                                fields["vcbs"] = ctext
                        elif ctag == "pIBSUF":
                            item["pibsuf"] = ctext
                            if not fields["pibsuf"]:
                                fields["pibsuf"] = ctext
                        elif ctag == "vIBSUF":
                            item["vibsuf"] = ctext
                            if not fields["vibsuf"]:
                                fields["vibsuf"] = ctext
                        elif ctag == "pIBSMun":
                            item["pibsmun"] = ctext
                            if not fields["pibsmun"]:
                                fields["pibsmun"] = ctext
                        elif ctag == "vIBSMun":
                            item["vibsmun"] = ctext
                            if not fields["vibsmun"]:
                                fields["vibsmun"] = ctext
                        elif ctag == "vIBS":
                            item["vibs"] = ctext
                            if not fields["vibs"]:
                                fields["vibs"] = ctext
                    if item:
                        items.append(item)

                # Extract IBSCBSTot totals
                if tag == "IBSCBSTot":
                    for child in elem.iter():
                        ctag = child.tag.split("}")[-1]
                        ctext = (child.text or "").strip()
                        if ctag == "vCBS" and not fields["tot_vcbs"]:
                            fields["tot_vcbs"] = ctext
                        elif ctag == "vIBS" and not fields["tot_vibs"]:
                            fields["tot_vibs"] = ctext

                # Top-level fields (outside IBSCBS)
                if tag == "NCM" and not fields["ncm"]:
                    fields["ncm"] = text
                elif tag == "CEST" and not fields["cest"]:
                    fields["cest"] = text

        except ET.ParseError as exc:
            parse_error = str(exc)

        fields["layout_tags"] = ",".join(
            t for t, present in layout_tags.items() if present
        )

        return json.dumps({
            "invoice_id": invoice_id,
            "s3_key": s3_key,
            "doc_type": doc_type,
            "parse_error": parse_error,
            "fields": fields,
            "items": items,
        })
