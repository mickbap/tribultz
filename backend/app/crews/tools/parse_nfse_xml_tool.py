from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tools.s3_tool import put_object


class ParseNFSeInput(BaseModel):
    xml_content: str = Field(
        description="NFS-e XML string to parse. Paste the full XML content."
    )


class ParseNFSeXMLTool(BaseTool):
    """
    Parse a NFS-e XML string, store raw XML in S3, and extract fiscal fields.
    tenant_id is injected at construction and never exposed to the LLM.
    """

    name: str = "parse_nfse_xml"
    description: str = (
        "Parse a NFS-e XML string. Extracts fiscal fields (CST, cClassTrib, "
        "CodigoServico, NCM) and stores the original XML in S3. "
        "Returns a JSON string with {invoice_id, s3_key, parse_error, fields}."
    )
    args_schema: Type[BaseModel] = ParseNFSeInput
    tenant_id: str  # injected at construction — never exposed to LLM

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
            )
        except Exception as exc:
            s3_key = f"(s3-unavailable: {exc})"

        # Extract fields — namespace-agnostic (NFS-e varies by municipality/provider)
        fields: dict[str, str] = {
            "cst": "",
            "cclasstrib": "",
            "codigo_servico": "",
            "ncm": "",
        }
        parse_error: str | None = None

        try:
            root = ET.fromstring(xml_content.strip())
            for elem in root.iter():
                tag = elem.tag.split("}")[-1]  # strip namespace prefix if present
                text = (elem.text or "").strip()
                if tag == "CST" and not fields["cst"]:
                    fields["cst"] = text
                elif tag == "cClassTrib" and not fields["cclasstrib"]:
                    fields["cclasstrib"] = text
                elif tag in ("CodigoServico", "CodigoServicoPrestado", "ItemListaServico") and not fields["codigo_servico"]:
                    fields["codigo_servico"] = text
                elif tag == "NCM" and not fields["ncm"]:
                    fields["ncm"] = text
        except ET.ParseError as exc:
            parse_error = str(exc)

        return json.dumps({
            "invoice_id": invoice_id,
            "s3_key": s3_key,
            "parse_error": parse_error,
            "fields": fields,
        })
