"""Unified XML validation endpoint — accepts raw XML, returns Findings/Evidence v1.1.

Supports NFS-e, NF-e, and NFC-e. Auto-detects document type from XML content.
Applies deterministic validation rules per NT 2025.002-RTC.

Rules 1-14: Single-document validation (format, calculation, structure)
Rules 15-18: Cross-validation (NCM, ClassTrib, CNPJ — S13)
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.data.ncm_codes import VALID_NCM_CODES
from app.models.auth import User

router = APIRouter(prefix="/api/v1", tags=["validate-xml"])

# ── CST table (NT 2025.002-RTC) ────────────────────────────────────────────

CST_TABLE: dict[str, dict[str, str | None]] = {
    "000": {"group": "gIBSCBS", "desc": "Tributação normal (ad valorem)"},
    "001": {"group": "gIBSCBS", "desc": "Tributação normal com redução"},
    "002": {"group": "gIBSCBSMono", "desc": "Tributação ad rem"},
    "070": {"group": None, "desc": "Imunidade / Isenção"},
    "200": {"group": "gIBSCBS", "desc": "Diferimento"},
    "410": {"group": None, "desc": "Suspensão"},
    "510": {"group": "gIBSCBS", "desc": "Crédito presumido"},
    "515": {"group": "gIBSCBS", "desc": "Crédito presumido especial"},
    "550": {"group": "gIBSCBS", "desc": "Regime específico"},
    "620": {"group": "gIBSCBSMono", "desc": "Monofásico"},
    "800": {"group": "gTransfCred", "desc": "Transferência de crédito"},
    "810": {"group": None, "desc": "Ressarcimento"},
    "811": {"group": "gAjusteCompet", "desc": "Ajuste de competência"},
    "830": {"group": "gEstornoCred", "desc": "Estorno de crédito"},
}

VALID_CST_CODES = set(CST_TABLE.keys())


# ── Schemas ─────────────────────────────────────────────────────────────────

class FindingWhere(BaseModel):
    field: str | None = None
    xpath: str | None = None
    snippet: str | None = None


class Finding(BaseModel):
    id: str
    severity: str  # FATAL | ALERT
    rule_id: str
    title: str
    where: FindingWhere
    recommendation: str
    evidence_ids: list[str]


class Evidence(BaseModel):
    id: str
    type: str  # xml | link | print
    label: str
    xpath: str | None = None
    snippet: str | None = None


class ValidationResult(BaseModel):
    job_id: str
    audit_id: str
    document_type: str  # NFSE | NFE | NFCE
    findings: list[Finding]
    evidences: list[Evidence]
    fatals: int
    alerts: int
    created_at: str


# ── XML helpers ─────────────────────────────────────────────────────────────

def _first_tag(xml: str, tags: list[str]) -> dict[str, Any] | None:
    """Extract first occurrence of any tag (exact match, not prefix)."""
    for tag in tags:
        m = re.search(rf"<{tag}(?=[\s>/])([^>]*)>([\s\S]*?)</{tag}>", xml, re.IGNORECASE)
        if m:
            return {"tag": tag, "value": m.group(2).strip(), "snippet": m.group(0), "index": m.start()}
    return None


def _all_tags(xml: str, tag: str) -> list[dict[str, Any]]:
    """Return all occurrences of a tag."""
    results = []
    for m in re.finditer(rf"<{tag}(?=[\s>/])([^>]*)>([\s\S]*?)</{tag}>", xml, re.IGNORECASE):
        results.append({"value": m.group(2).strip(), "snippet": m.group(0), "index": m.start()})
    return results


def _detect_doc_type(xml: str) -> str:
    if re.search(r"<mod>\s*65\s*</mod>", xml, re.IGNORECASE):
        return "NFCE"
    if re.search(r"<nfeProc[\s>]", xml, re.IGNORECASE) or re.search(r"<infNFe[\s>]", xml, re.IGNORECASE):
        return "NFE"
    return "NFSE"


def _is_nfe_layout(xml: str) -> bool:
    return bool(re.search(r"<IBSCBS[\s>]", xml, re.IGNORECASE) or re.search(r"<nfeProc[\s>]", xml, re.IGNORECASE))


def _xpath(tag: str, doc_type: str) -> str:
    base = "/NFS-e/infNfse" if doc_type == "NFSE" else "/nfeProc/NFe/infNFe"
    return f"{base}//{tag}"


def _fingerprint(xml: str) -> str:
    return hashlib.md5(xml.encode()).hexdigest()[:12]


# ── Validation engine ───────────────────────────────────────────────────────

def validate_xml(
    xml: str,
    doc_type: str | None = None,
    *,
    classtrib_results: dict[str, bool | None] | None = None,
    cnpj_result: tuple[bool, str] | None = None,
) -> ValidationResult:
    """Apply deterministic validation rules to XML. Returns structured result.

    Optional enrichment parameters (pre-fetched by async caller):
      classtrib_results: {code: True/False/None} from ClassTrib API batch lookup
      cnpj_result: (is_active: bool, status: str) from CNPJ API lookup
    """
    xml = xml.strip()
    if not doc_type:
        doc_type = _detect_doc_type(xml)

    fp = _fingerprint(xml)
    job_id = f"job_xml_{fp}"
    audit_id = f"audit_xml_{fp}"
    is_nfe = doc_type in ("NFE", "NFCE")
    has_ibscbs = _is_nfe_layout(xml)

    findings: list[Finding] = []
    evidences: list[Evidence] = []
    ev_ids: set[str] = set()

    def _add(f: Finding, e: Evidence) -> None:
        findings.append(f)
        if e.id not in ev_ids:
            evidences.append(e)
            ev_ids.add(e.id)

    # Extract fields — for NF-e, get CST from IBSCBS block
    ibscbs_block = _first_tag(xml, ["IBSCBS"])
    cst = _first_tag(ibscbs_block["snippet"], ["CST"]) if (has_ibscbs and ibscbs_block) else _first_tag(xml, ["CST"])
    c_class_trib = _first_tag(ibscbs_block["snippet"], ["cClassTrib"]) if (has_ibscbs and ibscbs_block) else _first_tag(xml, ["cClassTrib"])
    service_code = _first_tag(xml, ["CodigoServico", "cServ", "codigoServico"])
    ncm = _first_tag(xml, ["NCM"])
    cest = _first_tag(xml, ["CEST"])

    # NF-e IBSCBS fields
    vbc = _first_tag(xml, ["vBC"])
    p_cbs = _first_tag(xml, ["pCBS"])
    v_cbs = _first_tag(xml, ["vCBS"])
    p_ibs_uf = _first_tag(xml, ["pIBSUF"])
    v_ibs_uf = _first_tag(xml, ["vIBSUF"])
    p_ibs_mun = _first_tag(xml, ["pIBSMun"])
    v_ibs_mun = _first_tag(xml, ["vIBSMun"])
    v_ibs = _first_tag(xml, ["vIBS"])

    # NFS-e legacy fields
    valor_cbs = _first_tag(xml, ["ValorCBS", "vCBS"])
    valor_ibs = _first_tag(xml, ["ValorIBS", "vIBS"])
    aliq_cbs = _first_tag(xml, ["AliquotaCBS", "pCBS"])
    aliq_ibs = _first_tag(xml, ["AliquotaIBS", "pIBSUF", "pIBSMun"])
    base_calculo = _first_tag(xml, ["BaseCalculo", "vBC"])

    _first_tag(xml, ["IBSCBSTot"])  # totals checked via item-level rules

    # ── Rules 1-3: Format checks ────────────────────────────────────────────

    format_checks = [
        ("F_CST_LEN", "CST_3_DIGITS", "CST inválido (esperado 3 dígitos)", "CST", cst, r"^\d{3}$", False),
        ("F_CCLASSTRIB_LEN", "CCLASSTRIB_6_DIGITS", "ClassTrib incorreto (esperado 6 dígitos)", "cClassTrib", c_class_trib, r"^\d{6}$", False),
        ("F_SERVICE_CODE_LEN", "SERVICE_CODE_6_DIGITS", "Código de serviço inválido (esperado 6 dígitos)", "CodigoServico", service_code, r"^\d{6}$", is_nfe),
    ]

    for fid, rid, title, field, source, pattern, skip in format_checks:
        if skip:
            continue
        ev_id = f"E_XML_{fid.replace('F_', '')}"
        val = source["value"] if source else ""
        snip = source["snippet"] if source else f"<!-- Campo {field} não encontrado -->"
        xp = _xpath(source["tag"] if source else field, doc_type)
        if not re.match(pattern, val):
            _add(
                Finding(id=fid, severity="FATAL", rule_id=rid, title=title, where=FindingWhere(field=field, xpath=xp, snippet=snip), recommendation="Corrigir no ERP e reemitir.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"Trecho XML — {field}", xpath=xp, snippet=snip),
            )

    # ── Rule 4: CST_VALID (NF-e only) ───────────────────────────────────────

    if has_ibscbs and cst and re.match(r"^\d{3}$", cst["value"]) and cst["value"] not in VALID_CST_CODES:
        ev_id = "E_XML_CST_VALID"
        _add(
            Finding(id="F_CST_VALID", severity="FATAL", rule_id="CST_VALID", title=f'CST "{cst["value"]}" não é código válido conforme NT 2025.002-RTC', where=FindingWhere(field="CST", xpath=_xpath("CST", doc_type), snippet=cst["snippet"]), recommendation=f"CSTs válidos: {', '.join(sorted(VALID_CST_CODES))}.", evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="CST — código desconhecido", xpath=_xpath("CST", doc_type), snippet=cst["snippet"]),
        )

    # ── Rule 5: CST_GROUP_MATCH ──────────────────────────────────────────────

    if has_ibscbs and cst and re.match(r"^\d{3}$", cst["value"]) and cst["value"] in VALID_CST_CODES:
        expected_group = CST_TABLE[cst["value"]]["group"]
        if expected_group and not _first_tag(xml, [expected_group]):
            ev_id = "E_XML_CST_GROUP_MATCH"
            _add(
                Finding(id="F_CST_GROUP_MATCH", severity="FATAL", rule_id="CST_GROUP_MATCH", title=f'CST {cst["value"]} exige grupo <{expected_group}>', where=FindingWhere(field="IBSCBS", xpath=_xpath("IBSCBS", doc_type)), recommendation=f'CST {cst["value"]} requer <{expected_group}>. Preencher conforme NT 2025.002.', evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"CST {cst['value']} — grupo ausente", xpath=_xpath("IBSCBS", doc_type)),
            )

    # ── Rule 6: IBSCBS_MISSING ───────────────────────────────────────────────

    if has_ibscbs:
        if not ibscbs_block:
            ev_id = "E_XML_IBSCBS_MISSING"
            _add(
                Finding(id="F_IBSCBS_MISSING", severity="FATAL", rule_id="IBSCBS_MISSING", title="Grupo IBSCBS ausente — obrigatório conforme NT 2025.002", where=FindingWhere(field="IBSCBS", xpath=_xpath("imposto", doc_type)), recommendation="Informar grupo IBSCBS com CST, cClassTrib e campos de cálculo.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBSCBS — grupo ausente", xpath=_xpath("imposto", doc_type)),
            )
    else:
        has_legacy = all([valor_cbs, valor_ibs, aliq_cbs, aliq_ibs])
        if not has_legacy:
            ev_id = "E_XML_IBSCBS_MISSING"
            _add(
                Finding(id="F_IBSCBS_MISSING", severity="FATAL", rule_id="IBSCBS_MISSING", title="IBS/CBS ausentes na nota", where=FindingWhere(field="IBS/CBS", xpath=_xpath("Valores", doc_type)), recommendation="Informar alíquota e valor de IBS e CBS conforme LC 214.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBS/CBS — campos ausentes", xpath=_xpath("Valores", doc_type)),
            )

    # ── Rule 7: IBSCBS_CALC — CBS ───────────────────────────────────────────

    def _calc_check(tag_base: Any, tag_rate: Any, tag_val: Any, label: str, fid: str) -> None:
        if not (tag_base and tag_rate and tag_val):
            return
        try:
            base = float(tag_base["value"])
            rate = float(tag_rate["value"])
            declared = float(tag_val["value"])
        except (ValueError, TypeError):
            return
        expected = base * rate
        if abs(declared - expected) > 0.01:
            ev_id = f"E_XML_{fid}"
            _add(
                Finding(id=f"F_{fid}", severity="FATAL", rule_id="IBSCBS_CALC", title=f"{label} incorreto — R$ {declared:.2f} vs esperado R$ {expected:.2f}", where=FindingWhere(field=tag_val["tag"], xpath=_xpath(tag_val["tag"], doc_type), snippet=tag_val["snippet"]), recommendation=f"{label} deve ser base × alíquota = R$ {expected:.2f}.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"{label} — cálculo divergente", xpath=_xpath(tag_val["tag"], doc_type), snippet=tag_val["snippet"]),
            )

    if has_ibscbs:
        _calc_check(vbc, p_cbs, v_cbs, "CBS", "IBSCBS_CALC_CBS")
    else:
        _calc_check(base_calculo, aliq_cbs, valor_cbs, "CBS", "IBSCBS_CALC_CBS")
        _calc_check(base_calculo, aliq_ibs, valor_ibs, "IBS", "IBSCBS_CALC_IBS")

    # ── Rules 11-13: IBS split (NF-e only) ──────────────────────────────────

    if has_ibscbs:
        _calc_check(vbc, p_ibs_uf, v_ibs_uf, "IBS UF", "IBSCBS_UF_CALC")
        _calc_check(vbc, p_ibs_mun, v_ibs_mun, "IBS Municipal", "IBSCBS_MUN_CALC")

        # Split check: vIBS == vIBSUF + vIBSMun
        if v_ibs and v_ibs_uf and v_ibs_mun:
            try:
                total = float(v_ibs["value"])
                uf = float(v_ibs_uf["value"])
                mun = float(v_ibs_mun["value"])
                expected = uf + mun
                if abs(total - expected) > 0.01:
                    ev_id = "E_XML_IBSCBS_SPLIT"
                    _add(
                        Finding(id="F_IBSCBS_SPLIT", severity="FATAL", rule_id="IBSCBS_SPLIT", title=f"Split IBS incorreto — vIBS ({total:.2f}) ≠ vIBSUF ({uf:.2f}) + vIBSMun ({mun:.2f})", where=FindingWhere(field="vIBS", xpath=_xpath("vIBS", doc_type), snippet=v_ibs["snippet"]), recommendation=f"vIBS deve ser vIBSUF + vIBSMun = R$ {expected:.2f}.", evidence_ids=[ev_id]),
                        Evidence(id=ev_id, type="xml", label="IBS — split divergente", xpath=_xpath("vIBS", doc_type), snippet=v_ibs["snippet"]),
                    )
            except (ValueError, TypeError):
                pass

    # ── Rule 8-9: CEST ───────────────────────────────────────────────────────

    if not cest:
        ev_id = "E_XML_CEST_MISSING"
        _add(
            Finding(id="F_CEST_MISSING", severity="FATAL", rule_id="CEST_MISSING", title="CEST ausente", where=FindingWhere(field="CEST", xpath=_xpath("CEST", doc_type)), recommendation="Informar código CEST.", evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="CEST — ausente", xpath=_xpath("CEST", doc_type)),
        )
    elif not re.match(r"^\d{7}$", cest["value"]):
        ev_id = "E_XML_CEST_FORMAT"
        _add(
            Finding(id="F_CEST_FORMAT", severity="FATAL", rule_id="CEST_FORMAT", title=f'CEST inválido (esperado 7 dígitos, encontrado "{cest["value"]}")', where=FindingWhere(field="CEST", xpath=_xpath(cest["tag"], doc_type), snippet=cest["snippet"]), recommendation="CEST deve ter 7 dígitos.", evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="CEST — formato inválido", xpath=_xpath(cest["tag"], doc_type), snippet=cest["snippet"]),
        )

    # ── Rule 10: Layout ──────────────────────────────────────────────────────

    if is_nfe:
        missing = [t for t in ["emit", "det", "total"] if not _first_tag(xml, [t])]
        if missing:
            ev_id = "E_XML_LAYOUT_NFE"
            _add(
                Finding(id="F_LAYOUT_NFE", severity="FATAL", rule_id="LAYOUT_NFE", title=f"Estrutura NF-e incompleta — faltam: {', '.join(missing)}", where=FindingWhere(field="Estrutura XML", xpath=_xpath("infNFe", doc_type)), recommendation="NF-e deve conter emit, det e total.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="NF-e — estrutura incompleta", xpath=_xpath("infNFe", doc_type)),
            )
    else:
        missing = [t for t in ["Valores", "PrestadorServico", "TomadorServico"] if not _first_tag(xml, [t])]
        if missing:
            ev_id = "E_XML_LAYOUT_PORTAL"
            _add(
                Finding(id="F_LAYOUT_PORTAL", severity="FATAL", rule_id="LAYOUT_PORTAL", title=f"Layout fora do padrão — faltam: {', '.join(missing)}", where=FindingWhere(field="Estrutura XML", xpath=_xpath("infNfse", doc_type)), recommendation="Seguir layout do Portal Nacional.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="Layout — tags ausentes", xpath=_xpath("infNfse", doc_type)),
            )

    # ── Rule 15: NCM_FORMAT ──────────────────────────────────────────────────

    if ncm:
        if not re.match(r"^\d{8}$", ncm["value"]):
            ev_id = "E_XML_NCM_FORMAT"
            _add(
                Finding(id="F_NCM_FORMAT", severity="FATAL", rule_id="NCM_FORMAT", title=f'NCM inválido (esperado 8 dígitos, encontrado "{ncm["value"]}")', where=FindingWhere(field="NCM", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]), recommendation="NCM deve ter exatamente 8 dígitos conforme TIPI.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="NCM — formato inválido", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]),
            )

    # ── Rule 16: NCM_VALID ─────────────────────────────────────────────────

    if ncm and re.match(r"^\d{8}$", ncm["value"]) and ncm["value"] not in VALID_NCM_CODES:
        ev_id = "E_XML_NCM_VALID"
        _add(
            Finding(id="F_NCM_VALID", severity="FATAL", rule_id="NCM_VALID", title=f'NCM "{ncm["value"]}" não encontrado na tabela TIPI', where=FindingWhere(field="NCM", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]), recommendation="Verificar código NCM conforme Tabela TIPI vigente.", evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="NCM — código desconhecido", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]),
        )

    # ── Rule 17: CLASSTRIB_VALID (enrichment — requires API pre-fetch) ─────

    if classtrib_results and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        code = c_class_trib["value"]
        lookup = classtrib_results.get(code)
        if lookup is False:
            ev_id = "E_XML_CLASSTRIB_VALID"
            _add(
                Finding(id="F_CLASSTRIB_VALID", severity="FATAL", rule_id="CLASSTRIB_VALID", title=f'cClassTrib "{code}" não encontrado no registro SVRS', where=FindingWhere(field="cClassTrib", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]), recommendation="Verificar código cClassTrib no portal Conformidade Fácil (SVRS).", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="cClassTrib — não encontrado", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
            )
        elif lookup is None:
            ev_id = "E_XML_CLASSTRIB_UNAVAIL"
            _add(
                Finding(id="F_CLASSTRIB_UNAVAIL", severity="ALERT", rule_id="CLASSTRIB_VALID", title=f'cClassTrib "{code}" — API SVRS indisponível, verificação pendente', where=FindingWhere(field="cClassTrib", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]), recommendation="API SVRS temporariamente indisponível. Verifique manualmente.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="cClassTrib — API indisponível", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
            )

    # ── Rule 18: CNPJ_ACTIVE (enrichment — requires API pre-fetch) ─────────

    if cnpj_result is not None:
        is_active, cnpj_status = cnpj_result
        if not is_active and cnpj_status != "API_UNAVAILABLE":
            emit_cnpj = _first_tag(xml, ["CNPJ"])
            cnpj_val = emit_cnpj["value"] if emit_cnpj else "?"
            cnpj_snip = emit_cnpj["snippet"] if emit_cnpj else ""
            ev_id = "E_XML_CNPJ_ACTIVE"
            _add(
                Finding(id="F_CNPJ_ACTIVE", severity="FATAL", rule_id="CNPJ_ACTIVE", title=f'CNPJ {cnpj_val} com situação "{cnpj_status}" — não está ativa', where=FindingWhere(field="CNPJ", xpath=_xpath("CNPJ", doc_type), snippet=cnpj_snip), recommendation="Documento emitido por CNPJ com situação cadastral irregular. Verificar junto à Receita Federal.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="CNPJ — situação irregular", xpath=_xpath("CNPJ", doc_type), snippet=cnpj_snip),
            )
        elif not is_active and cnpj_status == "API_UNAVAILABLE":
            ev_id = "E_XML_CNPJ_UNAVAIL"
            _add(
                Finding(id="F_CNPJ_UNAVAIL", severity="ALERT", rule_id="CNPJ_ACTIVE", title="Verificação de CNPJ indisponível — API fora do ar", where=FindingWhere(field="CNPJ", xpath=_xpath("CNPJ", doc_type)), recommendation="APIs de consulta CNPJ temporariamente indisponíveis. Verifique manualmente.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="CNPJ — API indisponível", xpath=_xpath("CNPJ", doc_type)),
            )

    fatals = sum(1 for f in findings if f.severity == "FATAL")
    alerts = sum(1 for f in findings if f.severity == "ALERT")

    return ValidationResult(
        job_id=job_id,
        audit_id=audit_id,
        document_type=doc_type,
        findings=findings,
        evidences=evidences,
        fatals=fatals,
        alerts=alerts,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/validate/xml",
    response_model=ValidationResult,
    dependencies=[Depends(require_plan("starter", "profissional", "contador"))],
)
async def validate_xml_endpoint(
    file: UploadFile = File(None),
    xml_content: str = Form(None),
    document_type: str | None = Form(None),
    current_user: User = Depends(get_current_user),
) -> ValidationResult:
    """Validate an XML document (NFS-e, NF-e, or NFC-e) against fiscal rules.

    Accepts either a file upload or raw XML in form data.
    Auto-detects document type if not specified.
    Enriches validation with ClassTrib API + CNPJ status check.
    """
    if file:
        raw = await file.read()
        xml = raw.decode("utf-8")
    elif xml_content:
        xml = xml_content
    else:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Envie um arquivo XML ou xml_content.")

    doc_type = document_type if document_type in ("NFSE", "NFE", "NFCE") else None

    # Async enrichment: ClassTrib + CNPJ lookups
    classtrib_data = await _enrich_classtrib(xml)
    cnpj_data = await _enrich_cnpj(xml)

    return validate_xml(
        xml, doc_type,
        classtrib_results=classtrib_data,
        cnpj_result=cnpj_data,
    )


# ── Batch cross-check schemas ──────────────────────────────────────────────

class DuplicateGroup(BaseModel):
    """Group of documents that appear to be duplicates."""
    key: str  # "CNPJ:NF_NUMBER" or "CNPJ:DATE:AMOUNT"
    indices: list[int]
    reason: str


class CstAnomaly(BaseModel):
    """NCM code with inconsistent CST across documents."""
    ncm: str
    cst_values: list[str]
    doc_indices: list[int]
    severity: str  # FATAL or ALERT


class BatchStats(BaseModel):
    """Aggregate statistics for a batch of validated documents."""
    total_documents: int
    pass_count: int
    fail_count: int
    pass_rate: float
    total_fatals: int
    total_alerts: int
    total_findings: int
    unique_emitters: int
    unique_ncm_codes: int
    date_range: str | None = None


class BatchCrossCheckResult(BaseModel):
    """Cross-validation results across multiple documents."""
    duplicates: list[DuplicateGroup]
    cst_anomalies: list[CstAnomaly]
    stats: BatchStats
    risk_score: int  # 0-100
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL


class BatchDocSummary(BaseModel):
    """Summary of a single document for batch cross-check."""
    xml: str
    fatals: int = 0
    has_duplicate: bool = False
    has_cst_anomaly: bool = False
    has_inactive_cnpj: bool = False
    has_unknown_ncm: bool = False


def _extract_doc_metadata(xml: str) -> dict[str, Any]:
    """Extract metadata from XML for cross-check purposes."""
    emit_block = _first_tag(xml, ["emit", "PrestadorServico"])
    cnpj_tag = _first_tag(emit_block["snippet"], ["CNPJ"]) if emit_block else None
    cnpj = cnpj_tag["value"] if cnpj_tag else ""

    nf_num = _first_tag(xml, ["nNF", "Numero", "NumeroNfse"])
    nf_number = nf_num["value"] if nf_num else ""

    date_tag = _first_tag(xml, ["dhEmi", "DataEmissao", "dhRecbto"])
    date_str = date_tag["value"][:10] if date_tag else ""

    total_tag = _first_tag(xml, ["vNF", "ValorServicos", "vProd"])
    total = total_tag["value"] if total_tag else ""

    ncm_tags = _all_tags(xml, "NCM")
    ncm_codes = [t["value"] for t in ncm_tags if re.match(r"^\d{8}$", t["value"])]

    cst_tags = _all_tags(xml, "CST")
    cst_codes = [t["value"] for t in cst_tags if re.match(r"^\d{3}$", t["value"])]

    return {
        "cnpj": cnpj,
        "nf_number": nf_number,
        "date": date_str,
        "total": total,
        "ncm_codes": ncm_codes,
        "cst_codes": cst_codes,
    }


def batch_cross_check(documents: list[BatchDocSummary]) -> BatchCrossCheckResult:
    """Perform cross-validation across a batch of XML documents.

    Detects: duplicates, CST inconsistencies, calculates risk score.
    """
    metadata = [_extract_doc_metadata(doc.xml) for doc in documents]

    # ── Duplicate detection ────────────────────────────────────────────────
    duplicates: list[DuplicateGroup] = []

    # By CNPJ + NF number
    nf_groups: dict[str, list[int]] = {}
    for i, m in enumerate(metadata):
        if m["cnpj"] and m["nf_number"]:
            key = f'{m["cnpj"]}:{m["nf_number"]}'
            nf_groups.setdefault(key, []).append(i)
    for key, indices in nf_groups.items():
        if len(indices) > 1:
            duplicates.append(DuplicateGroup(
                key=key, indices=indices,
                reason="Mesmo CNPJ emitente + número da nota fiscal",
            ))

    # By CNPJ + date + total amount (possible split avoidance)
    amt_groups: dict[str, list[int]] = {}
    for i, m in enumerate(metadata):
        if m["cnpj"] and m["date"] and m["total"]:
            key = f'{m["cnpj"]}:{m["date"]}:{m["total"]}'
            amt_groups.setdefault(key, []).append(i)
    for key, indices in amt_groups.items():
        if len(indices) > 1:
            # Avoid flagging if already flagged as NF duplicate
            already_flagged = any(
                set(indices) == set(d.indices) for d in duplicates
            )
            if not already_flagged:
                duplicates.append(DuplicateGroup(
                    key=key, indices=indices,
                    reason="Mesmo CNPJ + data + valor total (possível duplicidade)",
                ))

    # ── CST consistency analysis ───────────────────────────────────────────
    cst_anomalies: list[CstAnomaly] = []

    # Group NCM → set of (CST, doc_index)
    ncm_cst_map: dict[str, dict[str, list[int]]] = {}
    for i, m in enumerate(metadata):
        for ncm, cst in zip(m["ncm_codes"], m["cst_codes"]):
            ncm_cst_map.setdefault(ncm, {}).setdefault(cst, []).append(i)

    for ncm, cst_groups in ncm_cst_map.items():
        if len(cst_groups) > 1:
            all_csts = sorted(cst_groups.keys())
            all_indices = sorted({i for idxs in cst_groups.values() for i in idxs})

            # CST 000 (normal) + 070 (exempt) = likely error → FATAL
            # Other mixes = ALERT
            severity = "ALERT"
            conflict_pairs = {("000", "070"), ("070", "000"), ("000", "410"), ("410", "000")}
            cst_set = set(all_csts)
            if len(cst_set) >= 2 and any(
                a in cst_set and b in cst_set for a, b in conflict_pairs
            ):
                severity = "FATAL"

            cst_anomalies.append(CstAnomaly(
                ncm=ncm,
                cst_values=all_csts,
                doc_indices=all_indices,
                severity=severity,
            ))

    # ── Batch statistics ───────────────────────────────────────────────────
    pass_count = sum(1 for d in documents if d.fatals == 0)
    fail_count = len(documents) - pass_count
    total_fatals = sum(d.fatals for d in documents)
    unique_emitters = len({m["cnpj"] for m in metadata if m["cnpj"]})
    unique_ncm = len({ncm for m in metadata for ncm in m["ncm_codes"]})
    dates = sorted({m["date"] for m in metadata if m["date"]})
    date_range = f"{dates[0]} — {dates[-1]}" if len(dates) >= 2 else (dates[0] if dates else None)

    stats = BatchStats(
        total_documents=len(documents),
        pass_count=pass_count,
        fail_count=fail_count,
        pass_rate=round(pass_count / max(len(documents), 1) * 100, 1),
        total_fatals=total_fatals,
        total_alerts=0,
        total_findings=total_fatals,
        unique_emitters=unique_emitters,
        unique_ncm_codes=unique_ncm,
        date_range=date_range,
    )

    # ── Risk score (0-100) ─────────────────────────────────────────────────
    score = 0
    if len(documents) > 0:
        score += int(fail_count / len(documents) * 50)
    if duplicates:
        score += 10
    if cst_anomalies:
        score += 10
    if any(a.severity == "FATAL" for a in cst_anomalies):
        score += 10
    unknown_ncm_ratio = sum(1 for d in documents if d.has_unknown_ncm) / max(len(documents), 1)
    if unknown_ncm_ratio > 0.5:
        score += 10
    if any(d.has_inactive_cnpj for d in documents):
        score += 10
    score = min(score, 100)

    risk_level = "LOW"
    if score > 75:
        risk_level = "CRITICAL"
    elif score > 50:
        risk_level = "HIGH"
    elif score > 25:
        risk_level = "MEDIUM"

    return BatchCrossCheckResult(
        duplicates=duplicates,
        cst_anomalies=cst_anomalies,
        stats=stats,
        risk_score=score,
        risk_level=risk_level,
    )


@router.post(
    "/validate/batch-cross-check",
    response_model=BatchCrossCheckResult,
    dependencies=[Depends(require_plan("profissional", "contador"))],
)
async def batch_cross_check_endpoint(
    documents: list[BatchDocSummary],
    current_user: User = Depends(get_current_user),
) -> BatchCrossCheckResult:
    """Cross-validate a batch of XML documents.

    Detects duplicates, CST inconsistencies across documents, and calculates
    a compliance risk score. Premium feature (Profissional/Contador plans).
    """
    if len(documents) < 2:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Envie ao menos 2 documentos para validação cruzada.")
    if len(documents) > 500:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Máximo de 500 documentos por lote.")

    return batch_cross_check(documents)


async def _enrich_classtrib(xml: str) -> dict[str, bool | None] | None:
    """Pre-fetch ClassTrib codes from XML for enrichment."""
    from app.services.classtrib_service import classtrib_service

    codes: set[str] = set()
    for m in re.finditer(r"<cClassTrib[^>]*>(\d{6})</cClassTrib>", xml, re.IGNORECASE):
        codes.add(m.group(1))
    if not codes:
        return None
    try:
        return await classtrib_service.batch_validate(codes)
    except Exception:
        return None


async def _enrich_cnpj(xml: str) -> tuple[bool, str] | None:
    """Pre-fetch emitter CNPJ status for enrichment."""
    from app.services.cnpj_validator import validate_cnpj as _validate_cnpj

    # Extract emitter CNPJ (first CNPJ in emit block, or first CNPJ in document)
    emit_block = _first_tag(xml, ["emit", "PrestadorServico"])
    if not emit_block:
        return None
    cnpj_tag = _first_tag(emit_block["snippet"], ["CNPJ"])
    if not cnpj_tag or not re.match(r"^\d{14}$", cnpj_tag["value"]):
        return None
    try:
        result = await _validate_cnpj(cnpj_tag["value"])
        return (result.valid and result.status == "ATIVA", result.status)
    except Exception:
        return None
