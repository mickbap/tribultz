"""Unified XML validation endpoint — accepts raw XML, returns Findings/Evidence v1.1.

Supports NFS-e, NF-e, and NFC-e. Auto-detects document type from XML content.
Applies deterministic validation rules per NT 2025.002-RTC.
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

def validate_xml(xml: str, doc_type: str | None = None) -> ValidationResult:
    """Apply deterministic validation rules to XML. Returns structured result."""
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
    _first_tag(xml, ["NCM"])  # NCM extracted but not validated (advisory only)
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
    return validate_xml(xml, doc_type)
