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
        cest = (fields.get("cest") or "").strip()
        base_calculo = (fields.get("base_calculo") or "").strip()
        aliquota_cbs = (fields.get("aliquota_cbs") or "").strip()
        valor_cbs = (fields.get("valor_cbs") or "").strip()
        aliquota_ibs = (fields.get("aliquota_ibs") or "").strip()
        valor_ibs = (fields.get("valor_ibs") or "").strip()
        layout_tags = (fields.get("layout_tags") or "").strip()

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
                "recommendation": "ClassTrib incorreto. Verificar código conforme categoria do negócio e reemitir.",
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

        # Rule 6: IBSCBS_MISSING — IBS/CBS fields must be present
        has_ibscbs = all([valor_cbs, valor_ibs, aliquota_cbs, aliquota_ibs])
        if not has_ibscbs:
            findings.append({
                "rule_id": "IBSCBS_MISSING",
                "severity": "FATAL",
                "field": "IBS/CBS",
                "xpath": "/NFS-e/infNfse//Valores",
                "snippet": "(Tags ValorCBS, ValorIBS, AliquotaCBS, AliquotaIBS não encontradas)",
                "recommendation": "Informar alíquota e valor de IBS (0,90%) e CBS (0,10%) conforme LC 214.",
            })

        # Rule 7: IBSCBS_CALC — IBS/CBS calculation must match base × rate
        if has_ibscbs and base_calculo:
            try:
                base_val = float(base_calculo)
                cbs_val = float(valor_cbs)
                ibs_val = float(valor_ibs)
                cbs_rate = float(aliquota_cbs)
                ibs_rate = float(aliquota_ibs)

                expected_cbs = base_val * cbs_rate
                if abs(cbs_val - expected_cbs) > 0.01:
                    findings.append({
                        "rule_id": "IBSCBS_CALC",
                        "severity": "FATAL",
                        "field": "ValorCBS",
                        "xpath": "/NFS-e/infNfse//ValorCBS",
                        "snippet": f"<ValorCBS>{valor_cbs}</ValorCBS>",
                        "recommendation": (
                            f"CBS deve ser Base ({base_val:.2f}) × Alíquota ({cbs_rate}) "
                            f"= R$ {expected_cbs:.2f}. Informado: R$ {cbs_val:.2f}. Corrigir valor."
                        ),
                    })

                expected_ibs = base_val * ibs_rate
                if abs(ibs_val - expected_ibs) > 0.01:
                    findings.append({
                        "rule_id": "IBSCBS_CALC",
                        "severity": "FATAL",
                        "field": "ValorIBS",
                        "xpath": "/NFS-e/infNfse//ValorIBS",
                        "snippet": f"<ValorIBS>{valor_ibs}</ValorIBS>",
                        "recommendation": (
                            f"IBS deve ser Base ({base_val:.2f}) × Alíquota ({ibs_rate}) "
                            f"= R$ {expected_ibs:.2f}. Informado: R$ {ibs_val:.2f}. Corrigir valor."
                        ),
                    })
            except ValueError:
                pass  # non-numeric values — skip calc check

        # Rule 8: CEST_MISSING — CEST must be present
        if not cest:
            findings.append({
                "rule_id": "CEST_MISSING",
                "severity": "FATAL",
                "field": "CEST",
                "xpath": "/NFS-e/infNfse//CEST",
                "snippet": "(não encontrado)",
                "recommendation": "Informar código CEST conforme nova classificação tributária.",
            })

        # Rule 9: CEST_FORMAT — CEST must be exactly 7 digits
        if cest and not re.fullmatch(r"\d{7}", cest):
            findings.append({
                "rule_id": "CEST_FORMAT",
                "severity": "FATAL",
                "field": "CEST",
                "xpath": "/NFS-e/infNfse//CEST",
                "snippet": f"<CEST>{cest}</CEST>",
                "recommendation": "CEST deve ter exatamente 7 dígitos no formato novo. Verificar código atualizado.",
            })

        # Rule 10: LAYOUT_PORTAL — required Portal Nacional structure
        required_layout = ["Valores", "PrestadorServico", "TomadorServico"]
        present_tags = set(layout_tags.split(",")) if layout_tags else set()
        missing_layout = [t for t in required_layout if t not in present_tags]
        if missing_layout:
            findings.append({
                "rule_id": "LAYOUT_PORTAL",
                "severity": "FATAL",
                "field": "Estrutura XML",
                "xpath": "/NFS-e/infNfse",
                "snippet": f"(Tags obrigatórias ausentes: {', '.join(missing_layout)})",
                "recommendation": "Documento deve seguir layout do Portal Nacional de NFS-e com todas as seções obrigatórias.",
            })

        return json.dumps({"invoice_id": invoice_id, "findings": findings})
