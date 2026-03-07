from __future__ import annotations

import json
import re
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class ValidateFiscalInput(BaseModel):
    invoice_id: str = Field(description="Invoice ID returned by parse_nfse_xml")
    fields_json: str = Field(
        description=(
            'JSON string of extracted fields from parse_nfse_xml, e.g. '
            '{"cst":"123","cclasstrib":"654321","codigo_servico":"123456",'
            '"ncm":"12345678","parse_error":null}'
        )
    )


class ValidateFiscalRulesTool(BaseTool):
    """
    Apply NFS-e fiscal validation rules (S6 Discovery Top 10) to extracted fields.
    Returns findings with severity FATAL or ALERT and actionable recommendations.
    """

    name: str = "validate_fiscal_rules"
    description: str = (
        "Apply NFS-e fiscal validation rules to extracted fields. "
        "Requires invoice_id and fields_json from parse_nfse_xml. "
        "Returns a JSON string with {invoice_id, findings[{rule_id, severity, "
        "field, xpath, snippet, recommendation}]}."
    )
    args_schema: Type[BaseModel] = ValidateFiscalInput

    def _run(self, invoice_id: str, fields_json: str) -> str:
        try:
            data = json.loads(fields_json)
        except json.JSONDecodeError:
            data = {}

        # fields may be nested under "fields" key (direct output from parse_nfse_xml)
        fields = data.get("fields", data)
        parse_error: str | None = data.get("parse_error")

        cst = (fields.get("cst") or "").strip()
        cclasstrib = (fields.get("cclasstrib") or "").strip()
        codigo_servico = (fields.get("codigo_servico") or "").strip()
        ncm = (fields.get("ncm") or "").strip()

        findings: list[dict] = []

        # Rule 1: XML_PARSE — must be well-formed (FATAL, checked first)
        if parse_error:
            findings.append({
                "rule_id": "XML_PARSE",
                "severity": "FATAL",
                "field": "documento",
                "xpath": "/",
                "snippet": parse_error,
                "recommendation": "XML inválido. Verificar arquivo ou colar o XML correto.",
            })

        # Rule 2: CST_3_DIGITS
        if not re.fullmatch(r"\d{3}", cst):
            findings.append({
                "rule_id": "CST_3_DIGITS",
                "severity": "FATAL",
                "field": "CST",
                "xpath": "/NFS-e/infNfse//CST",
                "snippet": f"<CST>{cst}</CST>" if cst else "(não encontrado)",
                "recommendation": "CST deve ter exatamente 3 dígitos. Corrigir no ERP e reemitir.",
            })

        # Rule 3: CCLASSTRIB_6_DIGITS
        if not re.fullmatch(r"\d{6}", cclasstrib):
            findings.append({
                "rule_id": "CCLASSTRIB_6_DIGITS",
                "severity": "FATAL",
                "field": "cClassTrib",
                "xpath": "/NFS-e/infNfse//cClassTrib",
                "snippet": f"<cClassTrib>{cclasstrib}</cClassTrib>" if cclasstrib else "(não encontrado)",
                "recommendation": "cClassTrib deve ter exatamente 6 dígitos. Corrigir no ERP e reemitir.",
            })

        # Rule 4: SERVICE_CODE_6_DIGITS
        if not re.fullmatch(r"\d{6}", codigo_servico):
            findings.append({
                "rule_id": "SERVICE_CODE_6_DIGITS",
                "severity": "FATAL",
                "field": "CodigoServico",
                "xpath": "/NFS-e/infNfse//CodigoServico",
                "snippet": f"<CodigoServico>{codigo_servico}</CodigoServico>" if codigo_servico else "(não encontrado)",
                "recommendation": "Código de serviço deve ter exatamente 6 dígitos. Corrigir no ERP e reemitir.",
            })

        # Rule 5: NCM_PLACEHOLDER
        if not ncm:
            findings.append({
                "rule_id": "NCM_PLACEHOLDER",
                "severity": "ALERT",
                "field": "NCM",
                "xpath": "/NFS-e/infNfse//NCM",
                "snippet": "(não encontrado)",
                "recommendation": "Revisar NCM conforme classificação vigente. Manter evidência de suporte.",
            })

        return json.dumps({"invoice_id": invoice_id, "findings": findings})
