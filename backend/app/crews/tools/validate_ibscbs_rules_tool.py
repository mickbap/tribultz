from __future__ import annotations

import json
import re
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.crews.tools.parse_nfe_xml_tool import CST_TABLE
from app.data.cest_ncm import lookup_ncm_st

VALID_CST_CODES = set(CST_TABLE.keys())


class ValidateIBSCBSInput(BaseModel):
    invoice_id: str = Field(description="Invoice ID returned by parse_nfe_xml")
    fields_json: str = Field(
        description=(
            "JSON string with extracted fields from parse_nfe_xml. "
            "Must include: doc_type, fields (cst, cclasstrib, ncm, cest, vbc, "
            "pcbs, vcbs, pibsuf, vibsuf, pibsmun, vibsmun, vibs, "
            "tot_vcbs, tot_vibs, layout_tags), items[]."
        )
    )


class ValidateIBSCBSRulesTool(BaseTool):
    """
    Apply NF-e/NFC-e IBSCBS validation rules (NT 2025.002-RTC) to extracted fields.
    Validates: CST codes, CST-group coherence, IBS UF/Municipal split, CBS/IBS
    calculations, IBSCBS totals, CEST, and NF-e layout structure.
    Returns findings with severity FATAL or ALERT and actionable recommendations.
    """

    name: str = "validate_ibscbs_rules"
    description: str = (
        "Apply NF-e/NFC-e IBSCBS validation rules (NT 2025.002-RTC). "
        "Validates 14 rules: CST validity, CST-group coherence, CST semantics, "
        "CBS calculation, IBS UF calculation, IBS Municipal calculation, "
        "IBS split (UF+Mun=total), IBSCBS totals, CEST, and NF-e layout. "
        "Requires invoice_id and fields_json from parse_nfe_xml. "
        "Returns JSON with {invoice_id, doc_type, findings[], summary}."
    )
    args_schema: Type[BaseModel] = ValidateIBSCBSInput
    transaction_id: str | None = None

    def _run(self, invoice_id: str, fields_json: str) -> str:
        try:
            data = json.loads(fields_json)
        except json.JSONDecodeError:
            data = {}

        fields = data.get("fields", data)
        items = data.get("items", [])
        doc_type = data.get("doc_type", "NFE")
        parse_error: str | None = data.get("parse_error")

        cst = (fields.get("cst") or "").strip()
        cclasstrib = (fields.get("cclasstrib") or "").strip()
        ncm = (fields.get("ncm") or "").strip()
        cest = (fields.get("cest") or "").strip()
        vbc = (fields.get("vbc") or "").strip()
        pcbs = (fields.get("pcbs") or "").strip()
        vcbs = (fields.get("vcbs") or "").strip()
        pibsuf = (fields.get("pibsuf") or "").strip()
        vibsuf = (fields.get("vibsuf") or "").strip()
        pibsmun = (fields.get("pibsmun") or "").strip()
        vibsmun = (fields.get("vibsmun") or "").strip()
        vibs = (fields.get("vibs") or "").strip()
        tot_vcbs = (fields.get("tot_vcbs") or "").strip()
        tot_vibs = (fields.get("tot_vibs") or "").strip()
        layout_tags = (fields.get("layout_tags") or "").strip()
        indpag = (fields.get("indpag") or "").strip()

        # CSTs que legitimamente não geram CBS/IBS (imunidade, suspensão, etc)
        NO_TAX_CSTS = {"070", "410", "800", "810", "811", "830"}

        findings: list[dict[str, str]] = []
        xpath_base = "/nfeProc/NFe/infNFe"

        # Rule 1: XML_PARSE
        if parse_error:
            findings.append({
                "rule_id": "XML_PARSE",
                "severity": "FATAL",
                "field": "documento",
                "xpath": "/",
                "snippet": parse_error,
                "recommendation": "XML invalido. Verificar arquivo ou colar o XML correto.",
            })

        # Rule 2: CST_3_DIGITS
        if not re.fullmatch(r"\d{3}", cst):
            findings.append({
                "rule_id": "CST_3_DIGITS",
                "severity": "FATAL",
                "field": "CST",
                "xpath": f"{xpath_base}//IBSCBS/CST",
                "snippet": f"<CST>{cst}</CST>" if cst else "(nao encontrado)",
                "recommendation": "CST deve ter exatamente 3 digitos. Corrigir no ERP e reemitir.",
            })

        # Rule 3: CCLASSTRIB_6_DIGITS
        if not re.fullmatch(r"\d{6}", cclasstrib):
            findings.append({
                "rule_id": "CCLASSTRIB_6_DIGITS",
                "severity": "FATAL",
                "field": "cClassTrib",
                "xpath": f"{xpath_base}//IBSCBS/cClassTrib",
                "snippet": f"<cClassTrib>{cclasstrib}</cClassTrib>" if cclasstrib else "(nao encontrado)",
                "recommendation": "ClassTrib incorreto. Verificar codigo conforme categoria do negocio.",
            })

        # Rule 4: CST_VALID — must be a known CST code
        if re.fullmatch(r"\d{3}", cst) and cst not in VALID_CST_CODES:
            findings.append({
                "rule_id": "CST_VALID",
                "severity": "FATAL",
                "field": "CST",
                "xpath": f"{xpath_base}//IBSCBS/CST",
                "snippet": f"<CST>{cst}</CST>",
                "recommendation": (
                    f"CST '{cst}' nao e codigo valido conforme NT 2025.002-RTC. "
                    f"CSTs validos: {', '.join(sorted(VALID_CST_CODES))}."
                ),
            })

        # Rule 5: CST_GROUP_MATCH — CST ↔ XML group coherence
        if cst in VALID_CST_CODES:
            expected_group = CST_TABLE[cst].get("group")
            if expected_group:
                present_tags = set(layout_tags.split(",")) if layout_tags else set()
                # Check if the expected group tag is present
                # gIBSCBS maps to IBSCBS presence, etc.
                group_tag_map = {
                    "gIBSCBS": "IBSCBS",
                    "gIBSCBSMono": "IBSCBS",
                    "gTransfCred": "IBSCBS",
                    "gAjusteCompet": "IBSCBS",
                    "gEstornoCred": "IBSCBS",
                }
                check_tag = group_tag_map.get(str(expected_group), str(expected_group))
                if check_tag not in present_tags:
                    findings.append({
                        "rule_id": "CST_GROUP_MATCH",
                        "severity": "FATAL",
                        "field": "IBSCBS",
                        "xpath": f"{xpath_base}//IBSCBS",
                        "snippet": f"<CST>{cst}</CST>",
                        "recommendation": (
                            f"CST {cst} ({CST_TABLE[cst].get('description')}) "
                            f"requer grupo XML <{expected_group}>. Preencher conforme NT 2025.002."
                        ),
                    })

        # Rule 5b: CST_SEMANTIC — 070/410 should not have tax > 0
        if cst in ("070", "410"):
            tax_val = _safe_float(vcbs)
            ibs_tax_val = _safe_float(vibs)
            if tax_val > 0 or ibs_tax_val > 0:
                findings.append({
                    "rule_id": "CST_SEMANTIC",
                    "severity": "FATAL",
                    "field": "IBS/CBS",
                    "xpath": f"{xpath_base}//IBSCBS",
                    "snippet": f"<CST>{cst}</CST> vCBS={vcbs} vIBS={vibs}",
                    "recommendation": (
                        f"CST {cst} ({CST_TABLE[cst].get('description')}) "
                        "nao deve ter valores tributarios > 0."
                    ),
                })

        # Rule 5c: MONOFASICO_ZERO — CST 620 downstream should not have tax > 0 (#277)
        if cst == "620":
            tax_val = _safe_float(vcbs)
            ibs_tax_val = _safe_float(vibs)
            if tax_val > 0 or ibs_tax_val > 0:
                findings.append({
                    "rule_id": "MONOFASICO_ZERO",
                    "severity": "FATAL",
                    "field": "IBS/CBS",
                    "xpath": f"{xpath_base}//IBSCBS",
                    "snippet": f"<CST>{cst}</CST> vCBS={vcbs} vIBS={vibs}",
                    "recommendation": (
                        "CST 620 (regime monofasico): o IBS/CBS e recolhido integralmente "
                        "pelo fabricante/importador. Operacoes downstream devem ter vCBS=0 e vIBS=0 "
                        "(Reg. CBS cap. 8 / Reg. IBS cap. 6). Valor > 0 indica duplo recolhimento."
                    ),
                })

        # Rule 6: IBSCBS_MISSING
        has_ibscbs = "IBSCBS" in (layout_tags.split(",") if layout_tags else [])
        if not has_ibscbs:
            findings.append({
                "rule_id": "IBSCBS_MISSING",
                "severity": "FATAL",
                "field": "IBSCBS",
                "xpath": f"{xpath_base}//imposto",
                "snippet": "(Grupo <IBSCBS> nao encontrado em <imposto>)",
                "recommendation": "Informar grupo IBSCBS com CST, cClassTrib e campos de calculo conforme NT 2025.002.",
            })

        # Rule 7: IBSCBS_CALC — CBS calculation (vCBS == vBC x pCBS)
        if vbc and pcbs and vcbs:
            base = _safe_float(vbc)
            rate = _safe_float(pcbs)
            declared = _safe_float(vcbs)
            if base > 0 and rate >= 0:
                expected = base * rate
                if abs(declared - expected) > 0.01:
                    findings.append({
                        "rule_id": "IBSCBS_CALC",
                        "severity": "FATAL",
                        "field": "vCBS",
                        "xpath": f"{xpath_base}//gCBS/vCBS",
                        "snippet": f"<vCBS>{vcbs}</vCBS>",
                        "recommendation": (
                            f"vCBS deve ser vBC ({base:.2f}) x pCBS ({rate}) "
                            f"= R$ {expected:.2f}. Informado: R$ {declared:.2f}."
                        ),
                    })

        # Rule 11: IBSCBS_UF_CALC — vIBSUF == vBC x pIBSUF
        if vbc and pibsuf and vibsuf:
            base = _safe_float(vbc)
            rate = _safe_float(pibsuf)
            declared = _safe_float(vibsuf)
            if base > 0 and rate >= 0:
                expected = base * rate
                if abs(declared - expected) > 0.01:
                    findings.append({
                        "rule_id": "IBSCBS_UF_CALC",
                        "severity": "FATAL",
                        "field": "vIBSUF",
                        "xpath": f"{xpath_base}//gIBSUF/vIBSUF",
                        "snippet": f"<vIBSUF>{vibsuf}</vIBSUF>",
                        "recommendation": (
                            f"vIBSUF deve ser vBC ({base:.2f}) x pIBSUF ({rate}) "
                            f"= R$ {expected:.2f}. Informado: R$ {declared:.2f}."
                        ),
                    })

        # Rule 12: IBSCBS_MUN_CALC — vIBSMun == vBC x pIBSMun
        if vbc and pibsmun and vibsmun:
            base = _safe_float(vbc)
            rate = _safe_float(pibsmun)
            declared = _safe_float(vibsmun)
            if base > 0 and rate >= 0:
                expected = base * rate
                if abs(declared - expected) > 0.01:
                    findings.append({
                        "rule_id": "IBSCBS_MUN_CALC",
                        "severity": "FATAL",
                        "field": "vIBSMun",
                        "xpath": f"{xpath_base}//gIBSMun/vIBSMun",
                        "snippet": f"<vIBSMun>{vibsmun}</vIBSMun>",
                        "recommendation": (
                            f"vIBSMun deve ser vBC ({base:.2f}) x pIBSMun ({rate}) "
                            f"= R$ {expected:.2f}. Informado: R$ {declared:.2f}."
                        ),
                    })

        # Rule 13: IBSCBS_SPLIT — vIBS == vIBSUF + vIBSMun
        if vibs and vibsuf and vibsmun:
            total = _safe_float(vibs)
            uf = _safe_float(vibsuf)
            mun = _safe_float(vibsmun)
            expected = uf + mun
            if abs(total - expected) > 0.01:
                findings.append({
                    "rule_id": "IBSCBS_SPLIT",
                    "severity": "FATAL",
                    "field": "vIBS",
                    "xpath": f"{xpath_base}//gIBSCBS/vIBS",
                    "snippet": f"vIBS={vibs} vIBSUF={vibsuf} vIBSMun={vibsmun}",
                    "recommendation": (
                        f"Split IBS incorreto: vIBS ({total:.2f}) != "
                        f"vIBSUF ({uf:.2f}) + vIBSMun ({mun:.2f}) = R$ {expected:.2f}."
                    ),
                })

        # Rule 14: IBSCBS_TOTAL — totals vs sum of items
        if len(items) > 0 and tot_vcbs:
            sum_vcbs = sum(_safe_float(it.get("vcbs", "0")) for it in items)
            declared_tot = _safe_float(tot_vcbs)
            if abs(declared_tot - sum_vcbs) > 0.01:
                findings.append({
                    "rule_id": "IBSCBS_TOTAL",
                    "severity": "FATAL",
                    "field": "IBSCBSTot/vCBS",
                    "xpath": f"{xpath_base}//total/IBSCBSTot/vCBS",
                    "snippet": f"<vCBS>{tot_vcbs}</vCBS> (total) vs soma itens={sum_vcbs:.2f}",
                    "recommendation": (
                        f"Total CBS ({declared_tot:.2f}) != soma dos itens ({sum_vcbs:.2f})."
                    ),
                })

        if len(items) > 0 and tot_vibs:
            sum_vibs = sum(_safe_float(it.get("vibs", "0")) for it in items)
            declared_tot = _safe_float(tot_vibs)
            if abs(declared_tot - sum_vibs) > 0.01:
                findings.append({
                    "rule_id": "IBSCBS_TOTAL",
                    "severity": "FATAL",
                    "field": "IBSCBSTot/vIBS",
                    "xpath": f"{xpath_base}//total/IBSCBSTot/vIBS",
                    "snippet": f"<vIBS>{tot_vibs}</vIBS> (total) vs soma itens={sum_vibs:.2f}",
                    "recommendation": (
                        f"Total IBS ({declared_tot:.2f}) != soma dos itens ({sum_vibs:.2f})."
                    ),
                })

        # Rule 8: CEST_MISSING (#275 fase 2)
        # Regulamento 30/abr/2026 + Convênio ICMS 142/2018: CEST é obrigatório
        # apenas para produtos sujeitos a Substituição Tributária. Cruzamos o
        # NCM declarado contra subset curado (app/data/cest_ncm.py):
        #   - NCM em segmento ST conhecido → FATAL (CEST realmente obrigatório)
        #   - NCM fora do subset → ALERT (subset não cobre 100% do Conv. 142,
        #     então tratamos como incerto, não como erro)
        if not cest:
            st_info = lookup_ncm_st(ncm)
            if st_info["is_st"]:
                segments_label = ", ".join(st_info["segments"]) or "ST"
                findings.append({
                    "rule_id": "CEST_MISSING",
                    "severity": "FATAL",
                    "field": "CEST",
                    "xpath": f"{xpath_base}//prod/CEST",
                    "snippet": f"NCM={ncm} (segmento ST: {segments_label}) sem CEST",
                    "recommendation": (
                        f"CEST obrigatório: NCM {ncm} pertence ao segmento de Substituição "
                        f"Tributária ({segments_label}, Convênio ICMS 142/2018). Informe o "
                        f"CEST correspondente em <prod/CEST>."
                    ),
                })
            else:
                findings.append({
                    "rule_id": "CEST_MISSING",
                    "severity": "ALERT",
                    "field": "CEST",
                    "xpath": f"{xpath_base}//prod/CEST",
                    "snippet": "(nao encontrado)",
                    "recommendation": (
                        f"CEST ausente. NCM {ncm} não consta no subset ST conhecido "
                        f"(Convênio ICMS 142/2018). Se o produto for sujeito a ST, informe "
                        f"o CEST; se não for, este aviso pode ser desconsiderado."
                    ),
                })

        # Rule 9: CEST_FORMAT
        if cest and not re.fullmatch(r"\d{7}", cest):
            findings.append({
                "rule_id": "CEST_FORMAT",
                "severity": "FATAL",
                "field": "CEST",
                "xpath": f"{xpath_base}//prod/CEST",
                "snippet": f"<CEST>{cest}</CEST>",
                "recommendation": "CEST deve ter exatamente 7 digitos.",
            })

        # Rule 9b: SPLIT_PAYMENT_INDPAG (#276)
        # Regulamento IBS cap. 5: operações com pagamento eletrônico sujeito a
        # split (indPag=3 Pix/TED, indPag=4 cartão) devem lançar CBS+IBS.
        # Exceção: CSTs sem tributo (070 imunidade, 410 suspensão, etc).
        if indpag in {"3", "4"}:
            try:
                v_cbs_num = float(vcbs or 0)
                v_ibs_num = float(vibs or 0)
            except ValueError:
                v_cbs_num = v_ibs_num = 0.0

            tax_total = v_cbs_num + v_ibs_num
            if tax_total == 0 and cst not in NO_TAX_CSTS:
                method = "Pix/TED" if indpag == "3" else "cartão"
                findings.append({
                    "rule_id": "SPLIT_PAYMENT_INDPAG",
                    "severity": "FATAL",
                    "field": "indPag",
                    "xpath": f"{xpath_base}//cobr/dup/indPag",
                    "snippet": f"<indPag>{indpag}</indPag> com vCBS=0 e vIBS=0",
                    "recommendation": (
                        f"Pagamento via {method} (indPag={indpag}) sujeito a split payment "
                        f"(Regulamento IBS cap. 5), mas a NF-e não lança CBS nem IBS. "
                        f"Confirme se o CST {cst or '(ausente)'} é apropriado ou ajuste "
                        f"vCBS/vIBS."
                    ),
                })

        # Rule 10b: LAYOUT_NFE — required NF-e structure
        required = ["emit", "det", "total"]
        present = set(layout_tags.split(",")) if layout_tags else set()
        missing = [t for t in required if t not in present]
        if missing:
            findings.append({
                "rule_id": "LAYOUT_NFE",
                "severity": "FATAL",
                "field": "Estrutura XML",
                "xpath": xpath_base,
                "snippet": f"(Tags obrigatorias ausentes: {', '.join(missing)})",
                "recommendation": "NF-e deve conter emit, det e total conforme layout padrao.",
            })

        # Rule: NCM advisory
        if not ncm:
            findings.append({
                "rule_id": "NCM_PLACEHOLDER",
                "severity": "ALERT",
                "field": "NCM",
                "xpath": f"{xpath_base}//prod/NCM",
                "snippet": "(nao encontrado)",
                "recommendation": "Revisar NCM conforme classificacao fiscal vigente.",
            })

        fatals = sum(1 for f in findings if f["severity"] == "FATAL")
        alerts = sum(1 for f in findings if f["severity"] == "ALERT")

        return json.dumps(
            {
                "invoice_id": invoice_id,
                "transaction_id": self.transaction_id,
                "doc_type": doc_type,
                "findings": findings,
                "summary": {
                    "total": len(findings),
                    "fatals": fatals,
                    "alerts": alerts,
                    "status": "FAIL" if fatals > 0 else "PASS",
                    "items_parsed": len(items),
                },
            }
        )


def _safe_float(value: str) -> float:
    """Parse a string to float, returning 0.0 on failure."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
