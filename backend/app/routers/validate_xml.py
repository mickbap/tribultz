"""Unified XML validation endpoint — accepts raw XML, returns Findings/Evidence v1.1.

Supports NFS-e, NF-e, and NFC-e. Auto-detects document type from XML content.
Applies deterministic validation rules per NT 2025.002-RTC.

Rules 1-14: Single-document validation (format, calculation, structure)
Rules 15-18: Cross-validation (NCM, ClassTrib, CNPJ — S13)
"""

from __future__ import annotations

import hashlib
import logging
import datetime as dt
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.documents import Document
from app.models.jobs import Job as JobModel
from app.tools import s3_tool, postgres_tool
from app.services.xml_correction_service import correct_xml
from app.api.plan_gate import require_plan, check_usage_limit, increment_usage
from app.data.ncm_codes import VALID_NCM_CODES
from app.data.classtrib_table import (
    classtrib_cst,
    classtrib_dfe_allowed,
    classtrib_expected_aliquota_2026,
    classtrib_expected_zero,
    classtrib_monofasico_grupos,
    classtrib_permite_cred_pres,
)
from app.data.cest_ncm import lookup_ncm_st

logger = logging.getLogger(__name__)

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


class RegimeComparison(BaseModel):
    """Side-by-side old-regime vs. new-regime totals extracted from the XML."""
    base_old: str | None = None      # vBC (ICMS base, ICMSTot block)
    base_new: str | None = None      # vBC (CBS/IBS base, IBSCBS block)
    icms: str | None = None          # vICMS
    pis: str | None = None           # vPIS
    cofins: str | None = None        # vCOFINS
    cbs: str | None = None           # vCBS
    ibs: str | None = None           # vIBS (total)
    total_old: str | None = None     # icms + pis + cofins
    total_new: str | None = None     # cbs + ibs
    delta: str | None = None         # total_new - total_old


class ValidationResult(BaseModel):
    job_id: str
    audit_id: str
    document_type: str  # NFSE | NFE | NFCE
    findings: list[Finding]
    evidences: list[Evidence]
    fatals: int
    alerts: int
    created_at: str
    regime_comparison: RegimeComparison | None = None


# ── XML helpers ─────────────────────────────────────────────────────────────

def _first_tag(xml: str, tags: list[str]) -> dict[str, Any] | None:
    """Extract first occurrence of any tag (exact match, not prefix)."""
    for tag in tags:
        m = re.search(rf"<{tag}(?=[\s>/])([^>]*)>([\s\S]*?)</{tag}>", xml, re.IGNORECASE)
        if m:
            return {"tag": tag, "value": m.group(2).strip(), "snippet": m.group(0), "index": m.start()}
    return None


def _suframa_dv_ok(inscricao: str) -> bool:
    """Valida o DV da Inscrição SUFRAMA (9 díg: 8 base + DV; módulo 11, pesos 2–9 da
    direita p/ esquerda; resto 0 ou 1 → DV 0). Usado pela regra SUFRAMA_DV (C22-20, #311)."""
    digits = "".join(c for c in (inscricao or "") if c.isdigit())
    if len(digits) != 9:
        return False
    weights = [9, 8, 7, 6, 5, 4, 3, 2]  # pesos 2–9 da direita p/ esquerda = 9..2 da esquerda
    total = sum(int(d) * w for d, w in zip(digits[:8], weights))
    calc = 11 - (total % 11)
    if calc >= 10:
        calc = 0
    return calc == int(digits[8])


def _to_float(value: str | None) -> float:
    """Parse a numeric string to float; returns 0.0 on missing/invalid input."""
    try:
        return float(value) if value is not None else 0.0
    except (ValueError, TypeError):
        return 0.0


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


def _parse_iso_date(v: str) -> "dt.date | None":
    """Data de emissão como `date`, ou None quando ausente/ilegível.

    None NÃO vira "hoje": assumir data faria uma regra com vigência futura
    disparar sobre documento cuja data não conhecemos.
    """
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", (v or "").strip())
    if not m:
        return None
    try:
        return dt.date.fromisoformat(m.group(1))
    except ValueError:
        return None


def _xpath(tag: str, doc_type: str) -> str:
    base = "/NFS-e/infNfse" if doc_type == "NFSE" else "/nfeProc/NFe/infNFe"
    return f"{base}//{tag}"


def _fingerprint(xml: str) -> str:
    return hashlib.md5(xml.encode()).hexdigest()[:12]


def _extract_regime_comparison(xml: str, has_ibscbs: bool) -> RegimeComparison | None:
    """Extract old-regime (ICMS/PIS/COFINS) and new-regime (CBS/IBS) monetary totals."""
    from decimal import Decimal, InvalidOperation

    def _val(tag_result: dict[str, Any] | None) -> Decimal | None:
        if not tag_result:
            return None
        try:
            return Decimal(tag_result["value"].replace(",", "."))
        except (InvalidOperation, KeyError):
            return None

    # Old regime — prefer ICMSTot block so we don't grab CBS/IBS vBC by mistake
    icms_tot = _first_tag(xml, ["ICMSTot"])
    icms_block = icms_tot["snippet"] if icms_tot else xml

    base_old = _val(_first_tag(icms_block, ["vBC"]))
    v_icms = _val(_first_tag(icms_block, ["vICMS"]))
    v_pis = _val(_first_tag(icms_block, ["vPIS"]))
    v_cofins = _val(_first_tag(icms_block, ["vCOFINS"]))

    # New regime — IBSCBS block
    ibscbs = _first_tag(xml, ["IBSCBS"])
    ibscbs_src = ibscbs["snippet"] if ibscbs else xml
    base_new = _val(_first_tag(ibscbs_src, ["vBC"])) if has_ibscbs else None
    v_cbs = _val(_first_tag(ibscbs_src, ["vCBS"])) if has_ibscbs else _val(_first_tag(xml, ["ValorCBS"]))
    v_ibs = _val(_first_tag(ibscbs_src, ["vIBS"])) if has_ibscbs else _val(_first_tag(xml, ["ValorIBS"]))

    # Skip if no useful data
    has_old = any(x is not None for x in [v_icms, v_pis, v_cofins])
    has_new = any(x is not None for x in [v_cbs, v_ibs])
    if not has_old and not has_new:
        return None

    zero = Decimal("0")
    total_old = (v_icms or zero) + (v_pis or zero) + (v_cofins or zero)
    total_new = (v_cbs or zero) + (v_ibs or zero)
    delta = total_new - total_old

    def _fmt(d: Decimal | None) -> str | None:
        return str(d.quantize(Decimal("0.01"))) if d is not None else None

    return RegimeComparison(
        base_old=_fmt(base_old),
        base_new=_fmt(base_new),
        icms=_fmt(v_icms),
        pis=_fmt(v_pis),
        cofins=_fmt(v_cofins),
        cbs=_fmt(v_cbs),
        ibs=_fmt(v_ibs),
        total_old=_fmt(total_old),
        total_new=_fmt(total_new),
        delta=_fmt(delta),
    )


# ── Validation engine ───────────────────────────────────────────────────────

# ── LC 227/2026 — regras de obrigação acessória ─────────────────────────────
# Quando pedagogical_mode_2026=True, findings dessas regras são downgraded
# de FATAL para WARNING com badge do período pedagógico.
_PEDAGOGICAL_ACCESSORY_RULES = {
    "CST_3_DIGITS", "CCLASSTRIB_6_DIGITS", "SERVICE_CODE_6_DIGITS",
    "CST_VALID", "CST_GROUP_MATCH", "CST_SEMANTIC",
    "CEST_MISSING", "CEST_FORMAT",
    "LAYOUT_NFE", "LAYOUT_PORTAL", "IMPORT_IBSCBS_REQUIRED",
    "NCM_FORMAT", "NCM_VALID", "CLASSTRIB_VALID",
    "IBSCBSTOT_MISSING",
}
# IBSCBS_MISSING (Rejeição 1115/UB12-10) NÃO está mais aqui: desde a NT 2025.002
# v1.51, sua severidade é WARNING incondicional (implementação em produção
# suspensa pela própria NT, não pelo Período Pedagógico) — ver Rule 6.

# CSTs que legitimamente não destacam IBS/CBS no estágio atual — imunidade/isenção
# (070), suspensão (410), diferimento (200, tributo postergado p/ operação seguinte)
# e transferência/ressarcimento/ajuste/estorno de crédito (800/810/811/830).
# Não exigem IBS/CBS destacado, inclusive em importação.
_NO_TAX_CSTS = {"070", "200", "410", "800", "810", "811", "830"}

_LC227_RECOMMENDATION = (
    " — Período Pedagógico art. 348, §§ 3º e 4º, da LC 214/2025 (incluídos pela LC 227/2026): "
    "se autuado exclusivamente por esta obrigação acessória, é notificado a regularizar em "
    "60 dias contados da notificação; o cumprimento extingue a penalidade."
)

# ── NT 2025.002 v1.40 — códigos de rejeição SEFAZ (#311) ─────────────────────
# Anota o código oficial de rejeição nas detecções que o antecipam (NF-e/NFC-e),
# para o usuário saber como a SEFAZ rejeitará. Precedente: Rejeição 1157.
_REJECTION_CODES = {
    "IBSCBS_MISSING": (
        " — SEFAZ: Rejeição 1115 (regra UB12-10): preenchimento de IBS/CBS obrigatório pela "
        "legislação desde 03/08/2026 (Regime Normal/CRT 3) e 04/01/2027 (Simples/MEI); a rejeição "
        "técnica na autorização está com implementação em produção SUSPENSA — \"implementação futura\", "
        "sem data (NT 2025.002 v1.51). Homologação segue ativa desde 01/07/2026."
    ),
    "CCLASSTRIB_6_DIGITS": (
        " — SEFAZ: Rejeição 1106 (regra LA01-30) / 960 (regra N12-110): cClassTrib obrigatório "
        "e com classificação tributária adequada (NT 2025.002 v1.40)."
    ),
    # Grupo W03 (Total da NF-e — IBS/CBS/IS) — #403
    "IBSCBSTOT_MISSING": (
        " — SEFAZ: Rejeição 1119 (regra W34-20): grupo de totais IBSCBSTot (W03) obrigatório quando "
        "algum item informa IBS/CBS — produção a partir de 03/08/2026 (Regime Normal/CRT 3) "
        "e 04/01/2027 (Simples/MEI), NT 2025.002 v1.40."
    ),
    "IBSCBSTOT_UNDUE": (
        " — SEFAZ: Rejeição 1118 (regra W34-10): grupo IBSCBSTot informado sem nenhum item "
        "com IBS/CBS (NT 2025.002 v1.40)."
    ),
    "IBSCBS_TOTAL": (
        " — SEFAZ: Rejeição 1091 (regra W56-10, total CBS) / 1085 (regra W47-10, total IBS): "
        "os totais do IBSCBSTot devem ser a soma dos campos correspondentes dos itens (NT 2025.002 v1.40)."
    ),
}


def _pedagogical_severity(rule_id: str, pedagogical_mode: bool) -> str:
    """Return 'WARNING' for accessory rules in pedagogical mode, 'FATAL' otherwise."""
    if pedagogical_mode and rule_id in _PEDAGOGICAL_ACCESSORY_RULES:
        return "WARNING"
    return "FATAL"


# ── Ato Conjunto RFB/CGIBS nº 1/2025 — janela sem penalidades ────────────────
# Art. 3º: penalidades por descumprimento de obrigações acessórias de IBS/CBS
# suspensas até o 1º dia do 4º mês subsequente à publicação da parte comum dos
# regulamentos (Decreto 12.955/2026 + Resolução CGIBS 6/2026, publicados em
# 30/04/2026). Sem multa para fatos geradores até 31/07/2026; a partir de
# 01/08/2026 a penalidade volta a ser aplicável → FATAL. Distinto e combinável
# com o pedagogical_mode (LC 214/2025 art. 348, incluído pela LC 227/2026), que é override manual.
_NO_PENALTY_WINDOW_START = "2026-01-01"
_NO_PENALTY_WINDOW_END = "2026-08-01"  # exclusivo: notas a partir desta data são penalizáveis

_ATO_CONJUNTO_RECOMMENDATION = (
    " — Período sem penalidades (Ato Conjunto RFB/CGIBS nº 1/2025, art. 3º): "
    "obrigação acessória de IBS/CBS sem multa para fatos geradores até 31/07/2026 "
    "(parte comum dos regulamentos publicada em 30/04/2026). "
    "A partir de 01/08/2026 a penalidade é aplicável."
)


def _within_no_penalty_window(emission_date: dict | None) -> bool:
    """True se a data de emissão (dhEmi/NFS-e) cai na janela sem penalidades do Ato Conjunto 1/25."""
    if not emission_date:
        return False
    date_part = emission_date["value"][:10]  # YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_part):
        return False
    # Comparação lexicográfica é válida para datas ISO YYYY-MM-DD.
    return _NO_PENALTY_WINDOW_START <= date_part < _NO_PENALTY_WINDOW_END


# ── Comunicado Conjunto CGIBS/RFB nº 01/2025 — CNPJ p/ PF contribuinte ───────
# Previa 01/07/2026; o Decreto 13.075/2026 (CBS, altera o Decreto 12.955/2026
# art. 239) e a Resolução CGIBS nº 13/2026 (IBS, altera o art. 617 do
# Regulamento do IBS/Resolução CGIBS nº 6/2026) adiaram, em conjunto, para
# 01/01/2027 a PF contribuinte de IBS/CBS ter que se inscrever no CNPJ e não
# poder emitir documento fiscal por CPF (LC 214 art. 251). O enquadramento
# como contribuinte não é verificável do XML → ALERT informativo (verificar
# enquadramento). Não editar sem checar se um ato mais recente adiou de novo.
_PF_CNPJ_REQUIRED_DATE = "2027-01-01"

# ── NF-e de devolução: referência à nota original por item via DFeReferenciado ──
# v1.40: a partir de 01/09/2026, a devolução (finNFe=4) referencia a nota original
# exclusivamente por item, via grupo DFeReferenciado (Rejeição 321 — VC02-14/VC03-20).
_DEVOLUCAO_DFEREF_DATE = "2026-09-01"

# ── Regime monofásico de combustíveis — grupo UB84 (gIBSCBSMono), NT 2025.002 v1.50 ──
# A partir de 04/01/2027, os subgrupos gMonoReten/gMonoRet/gMonoDif tornam-se
# obrigatórios quando o indicador correspondente do cClassTrib está ativo (fonte
# oficial SVRS). Antes da vigência → WARNING (antecipação); pedagogical_mode mantém
# WARNING (#404).
_MONOFASICO_GRUPO_UB_DATE = "2027-01-04"

# Tolerância do confronto de valores ad rem, em reais. Mesma do restante do motor
# (_calc_check, PIS/COFINS): a NT admite R$ 0,01 de diferença por arredondamento.
_MONOFASICO_AD_REM_TOL = 0.01

# Triplas (quantidade, alíquota ad rem, valor) conferidas em UB84 — #478.
#
# Ad rem é R$ POR UNIDADE, não percentual: `valor = quantidade × ad rem`, SEM
# dividir por 100. É a armadilha inversa da do #617, onde pCBS/pIBSUF eram
# percentuais e o motor tratava como fração. Quem for "uniformizar" os dois
# cálculos depois vai querer acrescentar /100 aqui — não acrescente; o teste
# `test_ad_rem_nao_divide_por_cem` existe para barrar isso.
#
# O subgrupo padrão aparece como `gMono` numa fonte e `gMonoPadrao` noutra, e a
# numeração de leiaute diverge entre fontes (UB90 vs UB91 para gMonoReten). Por
# isso a regra NÃO afirma qual subgrupo é obrigatório — isso é o gap ainda
# bloqueado do #478 — e apenas confere a aritmética onde os campos existirem.
# Assim ela é correta sob qualquer das leituras.
_MONOFASICO_AD_REM_TRIPLAS: list[tuple[str, str, str, str]] = [
    ("qBCMono", "adRemIBS", "vIBSMono", "IBS monofásico"),
    ("qBCMono", "adRemCBS", "vCBSMono", "CBS monofásica"),
    ("qBCMonoReten", "adRemIBSReten", "vIBSMonoReten", "IBS monofásico retido"),
    ("qBCMonoReten", "adRemCBSReten", "vCBSMonoReten", "CBS monofásica retida"),
    ("qBCMonoRet", "adRemIBSRet", "vIBSMonoRet", "IBS monofásico retido anteriormente"),
    ("qBCMonoRet", "adRemCBSRet", "vCBSMonoRet", "CBS monofásica retida anteriormente"),
]
# gMonoDif fica FORA: o diferimento usa percentual (pDifIBS/pDifCBS) sobre valor,
# não ad rem sobre quantidade — semântica diferente, e a base sobre a qual o
# percentual incide não foi confirmada em fonte verificável.

# ── DANFE Simplificado Tipo 2 (tpImp=6) — NT 2026.002 v1.00, fase 2 ────────────
# A partir de 03/08/2026 (produção), a NF-e (modelo 55) emitida com tpImp=6 (Ajuste
# SINIEF 13/2026) só é admitida em operações de saída, internas, sem referência a
# outro documento fiscal e com finalidade Normal — violação rejeita na SEFAZ
# (códigos 706/707/708/715, ver regra DANFE_SIMPLIFICADO_RESTRICAO, #405). Antes da vigência
# → WARNING (antecipação); pedagogical_mode mantém WARNING.
_DANFE_T2_PRODUCAO_DATE = "2026-08-03"


def validate_xml(
    xml: str,
    doc_type: str | None = None,
    *,
    classtrib_results: dict[str, bool | None] | None = None,
    cnpj_result: tuple[bool, str] | None = None,
    pedagogical_mode: bool = False,
) -> ValidationResult:
    """Apply deterministic validation rules to XML. Returns structured result.

    Optional enrichment parameters (pre-fetched by async caller):
      classtrib_results: {code: True/False/None} from ClassTrib API batch lookup
      cnpj_result: (is_active: bool, status: str) from CNPJ API lookup
      pedagogical_mode: when True, accessory-rule FATALs become WARNINGs
                        with LC 214/2025 art. 348 (incluído pela LC 227/2026) annotation
    """
    xml = xml.strip()
    if not doc_type:
        doc_type = _detect_doc_type(xml)

    fp = _fingerprint(xml)
    job_id = str(uuid4())
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

    # CRT do emitente (NT 2025.002 v1.40 #311): 1/2=Simples Nacional, 3=Regime Normal, 4=MEI
    crt = _first_tag(xml, ["CRT"])

    # dPrevEntrega fields (NT 2025.002 V1.36 + Cartilha CGIBS item 1.1)
    d_prev_entrega = _first_tag(xml, ["dPrevEntrega"])
    dh_emi = _first_tag(xml, ["dhEmi"])
    mod_frete = _first_tag(xml, ["modFrete"])

    # Data de emissão para a janela sem penalidades (Ato Conjunto 1/25): NF-e usa
    # dhEmi; NFS-e legado usa DataEmissao/dhEmissao/dhProc/dEmi.
    emission_date = dh_emi or _first_tag(xml, ["DataEmissao", "dhEmissao", "dhProc", "dEmi"])

    # NFS-e legacy fields
    valor_cbs = _first_tag(xml, ["ValorCBS", "vCBS"])
    valor_ibs = _first_tag(xml, ["ValorIBS", "vIBS"])
    aliq_cbs = _first_tag(xml, ["AliquotaCBS", "pCBS"])
    aliq_ibs = _first_tag(xml, ["AliquotaIBS", "pIBSUF", "pIBSMun"])
    base_calculo = _first_tag(xml, ["BaseCalculo", "vBC"])

    # NFS-e — grupo IBSCBS da DPS, NT 004 v2.00/005/007 (#406). indZFMALC sinaliza
    # operação com alíquota zero de CBS (Zona Franca de Manaus/Área de Livre
    # Comércio). vPis/vCofins: a partir da NT 007/2026 informam apenas o valor
    # DEVIDO (não retido).
    ind_zfmalc = _first_tag(xml, ["indZFMALC", "IndZFMALC"])
    v_pis = _first_tag(xml, ["vPis", "ValorPis"])
    v_cofins = _first_tag(xml, ["vCofins", "ValorCofins"])

    # Grupo "piscofins" (NFSe/infNFSe/DPS/infDPS/valores/trib/tribFed/piscofins) —
    # vBCPisCofins/pAliqPis/pAliqCofins são campos irmãos de vPis/vCofins, todos
    # opcionais (#480). Fórmula confirmada via fonte oficial + manual de integração
    # pós-NT007 (ver comentário na regra PIS_COFINS_DEVIDO_CALC abaixo).
    base_pis_cofins = _first_tag(xml, ["vBCPisCofins", "BaseCalculoPisCofins"])
    aliq_pis = _first_tag(xml, ["pAliqPis", "AliquotaPis"])
    aliq_cofins = _first_tag(xml, ["pAliqCofins", "AliquotaCofins"])

    ibscbs_tot = _first_tag(xml, ["IBSCBSTot"])  # grupo W03 (totais IBS/CBS) — #403

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
        sev = _pedagogical_severity(rid, pedagogical_mode)
        rec = "Corrigir no ERP e reemitir."
        if sev == "WARNING":
            rec += _LC227_RECOMMENDATION
        if not re.match(pattern, val):
            _add(
                Finding(id=fid, severity=sev, rule_id=rid, title=title, where=FindingWhere(field=field, xpath=xp, snippet=snip), recommendation=rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"Trecho XML — {field}", xpath=xp, snippet=snip),
            )

    # ── Rule 4: CST_VALID (NF-e only) ───────────────────────────────────────

    if has_ibscbs and cst and re.match(r"^\d{3}$", cst["value"]) and cst["value"] not in VALID_CST_CODES:
        ev_id = "E_XML_CST_VALID"
        _sev = _pedagogical_severity("CST_VALID", pedagogical_mode)
        _rec = f"CSTs válidos: {', '.join(sorted(VALID_CST_CODES))}."
        if _sev == "WARNING":
            _rec += _LC227_RECOMMENDATION
        _add(
            Finding(id="F_CST_VALID", severity=_sev, rule_id="CST_VALID", title=f'CST "{cst["value"]}" não é código válido conforme NT 2025.002-RTC', where=FindingWhere(field="CST", xpath=_xpath("CST", doc_type), snippet=cst["snippet"]), recommendation=_rec, evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="CST — código desconhecido", xpath=_xpath("CST", doc_type), snippet=cst["snippet"]),
        )

    # ── Rule 5: CST_GROUP_MATCH ──────────────────────────────────────────────

    if has_ibscbs and cst and re.match(r"^\d{3}$", cst["value"]) and cst["value"] in VALID_CST_CODES:
        expected_group = CST_TABLE[cst["value"]]["group"]
        if expected_group and not _first_tag(xml, [expected_group]):
            ev_id = "E_XML_CST_GROUP_MATCH"
            _sev = _pedagogical_severity("CST_GROUP_MATCH", pedagogical_mode)
            _rec = f'CST {cst["value"]} requer <{expected_group}>. Preencher conforme NT 2025.002.'
            if _sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_CST_GROUP_MATCH", severity=_sev, rule_id="CST_GROUP_MATCH", title=f'CST {cst["value"]} exige grupo <{expected_group}>', where=FindingWhere(field="IBSCBS", xpath=_xpath("IBSCBS", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"CST {cst['value']} — grupo ausente", xpath=_xpath("IBSCBS", doc_type)),
            )

    # ── Rule 6: IBSCBS_MISSING ───────────────────────────────────────────────

    # Rejeição 1115 (UB12-10, grupo IBSCBS ausente) — NT 2025.002 v1.51 (04/08/2026):
    # implementação em produção passou de "≥ 03/08/2026" para "implementação futura,
    # sem data". A obrigação legal (LC 214) e a multa por obrigação acessória (Ato
    # Conjunto RFB/CGIBS nº 1/2025, desde 01/08/2026) não mudaram — só a rejeição
    # técnica na autorização foi suspensa. WARNING incondicional: não depende mais de
    # CRT nem de pedagogical_mode (a suspensão é da própria NT, não do Período
    # Pedagógico art. 348 LC 214, que é um mecanismo distinto). IBSCBS_MISSING foi
    # retirado de _PEDAGOGICAL_ACCESSORY_RULES por não ser mais governado por ele.
    _crt_val = crt["value"].strip() if crt else ""
    _is_simples_mei = _crt_val in ("1", "2", "4")
    _ibscbs_sev = "WARNING"
    # NT 2025.002 v1.51 retirou do texto vigente a data técnica específica
    # (04/01/2027) pra Simples/MEI; cronograma futuro fica pra NT ainda não
    # publicada — citar só o marco legal (art. 348, LC 214) até lá.
    _simples_note = (
        " Simples Nacional/MEI: obrigatório a partir de 2027 (art. 348, LC 214/2025) —"
        " NT 2025.002 v1.51 retirou a data técnica específica do texto vigente; NT"
        " futura deve fixá-la."
    )
    _ibscbs_presenca_suspensa_note = (
        " Obrigatório pela legislação desde 03/08/2026 (Regime Normal/CRT 3); a rejeição"
        " técnica na autorização (UB12-10/Rejeição 1115) está com implementação em produção"
        ' SUSPENSA — "implementação futura", sem data (NT 2025.002 v1.51). A multa por'
        " obrigação acessória segue aplicável desde 01/08/2026 (Ato Conjunto RFB/CGIBS nº 1/2025)."
    )
    if has_ibscbs:
        if not ibscbs_block:
            ev_id = "E_XML_IBSCBS_MISSING"
            _rec = "Informar grupo IBSCBS com CST, cClassTrib e campos de cálculo." + _ibscbs_presenca_suspensa_note
            if _is_simples_mei:
                _rec += _simples_note
            _add(
                Finding(id="F_IBSCBS_MISSING", severity=_ibscbs_sev, rule_id="IBSCBS_MISSING", title="Grupo IBSCBS ausente — obrigatório conforme NT 2025.002", where=FindingWhere(field="IBSCBS", xpath=_xpath("imposto", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBSCBS — grupo ausente", xpath=_xpath("imposto", doc_type)),
            )
    else:
        has_legacy = all([valor_cbs, valor_ibs, aliq_cbs, aliq_ibs])
        if not has_legacy:
            ev_id = "E_XML_IBSCBS_MISSING"
            _rec = "Informar alíquota e valor de IBS e CBS conforme LC 214." + _ibscbs_presenca_suspensa_note
            if _is_simples_mei:
                _rec += _simples_note
            _add(
                Finding(id="F_IBSCBS_MISSING", severity=_ibscbs_sev, rule_id="IBSCBS_MISSING", title="IBS/CBS ausentes na nota", where=FindingWhere(field="IBS/CBS", xpath=_xpath("Valores", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBS/CBS — campos ausentes", xpath=_xpath("Valores", doc_type)),
            )

    # ── Rule 7: IBSCBS_CALC — CBS ───────────────────────────────────────────

    def _calc_check(
        tag_base: Any, tag_rate: Any, tag_val: Any, label: str, fid: str,
        *, rate_is_percent: bool = False,
    ) -> None:
        """Confere valor declarado contra base × alíquota.

        `rate_is_percent=True` para o grupo IBSCBS da NF-e/NFC-e, onde
        pCBS/pIBSUF/pIBSMun são declarados em PONTOS PERCENTUAIS (leiaute 3v2-4
        da NT 2025.002-RTC): pCBS=0.9000 é 0,9%, logo vBC=1000,00 → vCBS=9,00.
        #617: sem a divisão, o esperado saía 100× maior e reprovava com FATAL
        toda nota corretamente preenchida.

        O caminho legado de NFS-e (AliquotaCBS/AliquotaIBS, NT 007/2026) usa
        outras tags e permanece com `rate_is_percent=False` — a convenção
        daquele leiaute não foi verificada neste trabalho.
        """
        if not (tag_base and tag_rate and tag_val):
            return
        try:
            base = float(tag_base["value"])
            rate = float(tag_rate["value"])
            declared = float(tag_val["value"])
        except (ValueError, TypeError):
            return
        expected = (base * rate / 100) if rate_is_percent else (base * rate)
        if abs(declared - expected) > 0.01:
            ev_id = f"E_XML_{fid}"
            _add(
                Finding(id=f"F_{fid}", severity="FATAL", rule_id="IBSCBS_CALC", title=f"{label} incorreto — R$ {declared:.2f} vs esperado R$ {expected:.2f}", where=FindingWhere(field=tag_val["tag"], xpath=_xpath(tag_val["tag"], doc_type), snippet=tag_val["snippet"]), recommendation=f"{label} deve ser base × alíquota = R$ {expected:.2f}.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"{label} — cálculo divergente", xpath=_xpath(tag_val["tag"], doc_type), snippet=tag_val["snippet"]),
            )

    if has_ibscbs:
        _calc_check(vbc, p_cbs, v_cbs, "CBS", "IBSCBS_CALC_CBS", rate_is_percent=True)
    else:
        _calc_check(base_calculo, aliq_cbs, valor_cbs, "CBS", "IBSCBS_CALC_CBS")
        _calc_check(base_calculo, aliq_ibs, valor_ibs, "IBS", "IBSCBS_CALC_IBS")

    # ── Rule: INDZFMALC_CBS_ZERO — indZFMALC ativo exige CBS zero (NFS-e, NT 007/2026, #406) ──
    # indZFMALC sinaliza operação sob benefício de alíquota zero de CBS (ZFM/ALC, LC
    # 214/2025). Sem esta checagem, o motor não teria como evitar falso-positivo
    # (cobrar CBS) nem falso-negativo (não notar CBS indevidamente cobrado) numa
    # operação ZFM/ALC legítima. WARNING: a própria plataforma nacional NFS-e ainda
    # não valida este campo (preenchimento com validação desativada) — nosso valor
    # é sinalizar o que a plataforma ainda não sinaliza, não reproduzir rejeição dura.
    if doc_type == "NFSE" and ind_zfmalc and ind_zfmalc["value"].strip().lower() in ("1", "true", "s", "sim"):
        _zfmalc_cbs = valor_cbs if not has_ibscbs else v_cbs
        if _zfmalc_cbs:
            try:
                _zfmalc_cbs_val = float(_zfmalc_cbs["value"])
            except (ValueError, TypeError):
                _zfmalc_cbs_val = 0.0
            if _zfmalc_cbs_val > 0.01:
                ev_id = "E_XML_INDZFMALC_CBS_ZERO"
                _add(
                    Finding(
                        id="F_INDZFMALC_CBS_ZERO", severity="WARNING", rule_id="INDZFMALC_CBS_ZERO",
                        title=f'indZFMALC ativo, mas CBS = R$ {_zfmalc_cbs_val:.2f} (esperado zero)',
                        where=FindingWhere(field=_zfmalc_cbs["tag"], xpath=_xpath(_zfmalc_cbs["tag"], doc_type), snippet=_zfmalc_cbs["snippet"]),
                        recommendation=(
                            "indZFMALC indica operação com benefício de alíquota zero de CBS "
                            "(Zona Franca de Manaus/Área de Livre Comércio, LC 214/2025, art. sobre ZFM/ALC). "
                            "Com o indicador ativo, o valor de CBS deve ser zero. "
                            "NT 007/2026 (SE/CGNFS-e) — validação ainda desativada na plataforma nacional; "
                            "checagem preventiva do Tribultz."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="indZFMALC × CBS incoerente", xpath=_xpath(_zfmalc_cbs["tag"], doc_type), snippet=_zfmalc_cbs["snippet"]),
                )

    # ── Rule: PIS_COFINS_DEVIDO_NEGATIVO — vPis/vCofins devidos não podem ser < 0 (NT 007/2026, #406) ──
    # A partir da NT 007/2026, vPis/vCofins informam apenas o valor DEVIDO (não mais
    # retido) — um valor devido negativo é logicamente incoerente. Checagem de formato
    # mínima, independente da checagem de valor exato (PIS_COFINS_DEVIDO_CALC, #480).
    for _tag_result, _label, _fid in ((v_pis, "vPis", "PIS_COFINS_DEVIDO_NEGATIVO_PIS"), (v_cofins, "vCofins", "PIS_COFINS_DEVIDO_NEGATIVO_COFINS")):
        if _tag_result:
            try:
                _val = float(_tag_result["value"])
            except (ValueError, TypeError):
                continue
            if _val < 0:
                ev_id = f"E_XML_{_fid}"
                _add(
                    Finding(
                        id=f"F_{_fid}", severity="WARNING", rule_id="PIS_COFINS_DEVIDO_NEGATIVO",
                        title=f"{_label} negativo (R$ {_val:.2f}) — a partir da NT 007/2026 informa valor devido, não retenção",
                        where=FindingWhere(field=_tag_result["tag"], xpath=_xpath(_tag_result["tag"], doc_type), snippet=_tag_result["snippet"]),
                        recommendation=(
                            f"{_label} passou a informar apenas o valor DEVIDO (NT 007/2026, SE/CGNFS-e) — "
                            "um valor devido não pode ser negativo. Se o XML ainda trata este campo como "
                            "retenção (semântica anterior), corrija para o valor devido."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label=f"{_label} — valor devido negativo", xpath=_xpath(_tag_result["tag"], doc_type), snippet=_tag_result["snippet"]),
                )

    # ── Rule: PIS_COFINS_DEVIDO_CALC — vPis/vCofins = base × alíquota (NT 007/2026, #480) ──
    # Fórmula confirmada por fonte verificável (não especulada): a NT 007/2026
    # (SE/CGNFS-e, 07/02/2026) atualiza o grupo "piscofins" (CST + tpRetPisCofins),
    # mas não altera os campos pré-existentes vBCPisCofins/pAliqPis/pAliqCofins —
    # confirmados via manual de integração NFS-e pós-NT007 e corroborados de forma
    # independente (FocusNFe). Exemplo oficial: vBCPisCofins=988.33, pAliqPis=1.65
    # (%) → vPis=16.31 (988.33 × 1.65 / 100, arredondamento bancário) — bate exato.
    # Alíquotas em formato percentual (1.65 = 1,65%), não fração — por isso ÷100,
    # ao contrário de IBSCBS_CALC (que usa fração). Tolerância R$0,01 (oficial).
    # Campos opcionais — regra só dispara quando base e alíquota estão presentes
    # (mesma degradação graciosa do IBSCBS_CALC). WARNING: a plataforma nacional
    # NFS-e ainda não valida estes campos.
    for _aliq, _declared, _label, _fid in (
        (aliq_pis, v_pis, "vPis", "PIS_COFINS_DEVIDO_CALC_PIS"),
        (aliq_cofins, v_cofins, "vCofins", "PIS_COFINS_DEVIDO_CALC_COFINS"),
    ):
        if base_pis_cofins and _aliq and _declared:
            try:
                _base = float(base_pis_cofins["value"])
                _rate = float(_aliq["value"])
                _val = float(_declared["value"])
            except (ValueError, TypeError):
                continue
            _expected = (_base * _rate) / 100
            if abs(_val - _expected) > 0.01:
                ev_id = f"E_XML_{_fid}"
                _add(
                    Finding(
                        id=f"F_{_fid}", severity="WARNING", rule_id="PIS_COFINS_DEVIDO_CALC",
                        title=f"{_label} incorreto — informado R$ {_val:.2f}, esperado R$ {_expected:.2f}",
                        where=FindingWhere(field=_declared["tag"], xpath=_xpath(_declared["tag"], doc_type), snippet=_declared["snippet"]),
                        recommendation=(
                            f"{_label} deve ser base de cálculo (R$ {_base:.2f}) × alíquota ({_rate:.2f}%) = "
                            f"R$ {_expected:.2f} (NT 007/2026, tolerância R$ 0,01, arredondamento bancário). "
                            "Validação ainda desativada na plataforma nacional NFS-e."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label=f"{_label} — cálculo divergente", xpath=_xpath(_declared["tag"], doc_type), snippet=_declared["snippet"]),
                )

    # ── Rules 11-13: IBS split (NF-e only) ──────────────────────────────────

    if has_ibscbs:
        _calc_check(vbc, p_ibs_uf, v_ibs_uf, "IBS UF", "IBSCBS_UF_CALC", rate_is_percent=True)
        _calc_check(vbc, p_ibs_mun, v_ibs_mun, "IBS Municipal", "IBSCBS_MUN_CALC", rate_is_percent=True)

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

    # ── Rules 14/14b/14c: W03 — IBSCBSTot, presença e consistência (#403) ────
    # Grupo W03 (Total da NF-e — IBS/CBS/IS), NT 2025.002 v1.40. _all_tags("IBSCBS")
    # não casa <IBSCBSTot> (o padrão exige espaço/>/ após o nome da tag).

    if has_ibscbs:
        _item_ibscbs = _all_tags(xml, "IBSCBS")

        # W34-20 → Rejeição 1119: item informa IBS/CBS mas IBSCBSTot ausente.
        # Severidade faseada por CRT, como IBSCBS_MISSING (03/08/2026 vs 04/01/2027).
        if _item_ibscbs and not ibscbs_tot:
            _w03_sev = "WARNING" if _is_simples_mei else _pedagogical_severity("IBSCBSTOT_MISSING", pedagogical_mode)
            ev_id = "E_XML_IBSCBSTOT_MISSING"
            _rec = (
                "Informar <IBSCBSTot> em <total> com o somatório dos campos de IBS/CBS dos itens "
                "(vBCIBSCBS, gIBS, gCBS) conforme NT 2025.002."
            )
            if _is_simples_mei:
                _rec += _simples_note
            elif _w03_sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_IBSCBSTOT_MISSING", severity=_w03_sev, rule_id="IBSCBSTOT_MISSING", title="Grupo de totais IBSCBSTot (W03) ausente — itens informam IBS/CBS", where=FindingWhere(field="IBSCBSTot", xpath=_xpath("total", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBSCBSTot (W03) — grupo ausente", xpath=_xpath("total", doc_type)),
            )

        # W34-10 → Rejeição 1118: IBSCBSTot informado sem nenhum item com IBS/CBS.
        # Inconsistência (não faseamento) — FATAL sempre, como IBSCBS_SPLIT.
        if ibscbs_tot and not _item_ibscbs:
            ev_id = "E_XML_IBSCBSTOT_UNDUE"
            _add(
                Finding(id="F_IBSCBSTOT_UNDUE", severity="FATAL", rule_id="IBSCBSTOT_UNDUE", title="Grupo IBSCBSTot (W03) informado indevidamente — nenhum item possui IBS/CBS", where=FindingWhere(field="IBSCBSTot", xpath=_xpath("IBSCBSTot", doc_type), snippet=ibscbs_tot["snippet"]), recommendation="Remover <IBSCBSTot> ou informar o grupo IBSCBS nos itens correspondentes conforme NT 2025.002.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="IBSCBSTot (W03) — informado sem itens IBS/CBS", xpath=_xpath("IBSCBSTot", doc_type), snippet=ibscbs_tot["snippet"]),
            )

        # W56-10 → 1091 / W47-10 → 1085: totais devem ser a soma dos itens.
        # Espelha o frontend (xmlRules.ts, Rule 14): a última ocorrência de vCBS/vIBS
        # no documento é a do IBSCBSTot (totais vêm depois dos itens no leiaute).
        if ibscbs_tot and _item_ibscbs:
            def _tot_sum_check(tag: str, label: str, fid_suffix: str) -> None:
                tot_field = _first_tag(ibscbs_tot["snippet"], [tag])
                occurrences = _all_tags(xml, tag)
                det_values = occurrences[:-1] if tot_field else occurrences
                if not (tot_field and det_values):
                    return
                try:
                    declared = float(tot_field["value"])
                    soma = sum(float(o["value"]) for o in det_values if o["value"])
                except (ValueError, TypeError):
                    return
                if abs(declared - soma) > 0.01:
                    ev_id = f"E_XML_IBSCBS_TOTAL_{fid_suffix}"
                    _add(
                        Finding(id=f"F_IBSCBS_TOTAL_{fid_suffix}", severity="FATAL", rule_id="IBSCBS_TOTAL", title=f"Total {label} ({declared:.2f}) ≠ soma dos itens ({soma:.2f})", where=FindingWhere(field=f"IBSCBSTot/{tag}", xpath=_xpath("IBSCBSTot", doc_type), snippet=tot_field["snippet"]), recommendation=f"IBSCBSTot.{tag} deve ser a soma dos {tag} de cada item.", evidence_ids=[ev_id]),
                        Evidence(id=ev_id, type="xml", label=f"Total {label} — divergente", xpath=_xpath("IBSCBSTot", doc_type), snippet=tot_field["snippet"]),
                    )

            _tot_sum_check("vCBS", "CBS", "CBS")
            _tot_sum_check("vIBS", "IBS", "IBS")

    # ── Rule 8-9: CEST ───────────────────────────────────────────────────────

    if not cest:
        ev_id = "E_XML_CEST_MISSING"
        ncm_val = ncm["value"] if ncm else ""
        st_lookup = lookup_ncm_st(ncm_val)

        if st_lookup["is_st"]:
            seg_label = ", ".join(st_lookup["segments"])
            _add(
                Finding(id="F_CEST_MISSING", severity="FATAL", rule_id="CEST_MISSING", title=f"CEST obrigatório — NCM {ncm_val} pertence a segmento ST ({seg_label})", where=FindingWhere(field="CEST", xpath=_xpath("CEST", doc_type)), recommendation=f"NCM {ncm_val} consta no Convênio ICMS 142/2018 ({seg_label}). Informe o CEST correspondente em <prod/CEST>.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label=f"CEST obrigatório (segmento ST: {seg_label})", xpath=_xpath("CEST", doc_type)),
            )
        else:
            _add(
                Finding(id="F_CEST_MISSING", severity="ALERT", rule_id="CEST_MISSING", title="CEST ausente — verificar se produto é sujeito à substituição tributária", where=FindingWhere(field="CEST", xpath=_xpath("CEST", doc_type)), recommendation=f"NCM {ncm_val or '(não informado)'} não consta no subset ST conhecido (Convênio ICMS 142/2018). Se for sujeito a ST, informe o CEST; caso contrário, este aviso pode ser desconsiderado.", evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="CEST — ausente (verificar ST)", xpath=_xpath("CEST", doc_type)),
            )
    elif not re.match(r"^\d{7}$", cest["value"]):
        ev_id = "E_XML_CEST_FORMAT"
        _sev = _pedagogical_severity("CEST_FORMAT", pedagogical_mode)
        _rec = "CEST deve ter 7 dígitos."
        if _sev == "WARNING":
            _rec += _LC227_RECOMMENDATION
        _add(
            Finding(id="F_CEST_FORMAT", severity=_sev, rule_id="CEST_FORMAT", title=f'CEST inválido (esperado 7 dígitos, encontrado "{cest["value"]}")', where=FindingWhere(field="CEST", xpath=_xpath(cest["tag"], doc_type), snippet=cest["snippet"]), recommendation=_rec, evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="CEST — formato inválido", xpath=_xpath(cest["tag"], doc_type), snippet=cest["snippet"]),
        )

    # ── Rule 10: Layout ──────────────────────────────────────────────────────

    if is_nfe:
        missing = [t for t in ["emit", "det", "total"] if not _first_tag(xml, [t])]
        if missing:
            ev_id = "E_XML_LAYOUT_NFE"
            _sev = _pedagogical_severity("LAYOUT_NFE", pedagogical_mode)
            _rec = "NF-e deve conter emit, det e total."
            if _sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_LAYOUT_NFE", severity=_sev, rule_id="LAYOUT_NFE", title=f"Estrutura NF-e incompleta — faltam: {', '.join(missing)}", where=FindingWhere(field="Estrutura XML", xpath=_xpath("infNFe", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="NF-e — estrutura incompleta", xpath=_xpath("infNFe", doc_type)),
            )
    else:
        missing = [t for t in ["Valores", "PrestadorServico", "TomadorServico"] if not _first_tag(xml, [t])]
        if missing:
            ev_id = "E_XML_LAYOUT_PORTAL"
            _sev = _pedagogical_severity("LAYOUT_PORTAL", pedagogical_mode)
            _rec = "Seguir layout do Portal Nacional."
            if _sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_LAYOUT_PORTAL", severity=_sev, rule_id="LAYOUT_PORTAL", title=f"Layout fora do padrão — faltam: {', '.join(missing)}", where=FindingWhere(field="Estrutura XML", xpath=_xpath("infNfse", doc_type)), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="Layout — tags ausentes", xpath=_xpath("infNfse", doc_type)),
            )

    # ── Rules NT 2025.002 V1.36: dPrevEntrega (Cartilha CGIBS item 1.1) ────────
    # Determina o período de apuração do IBS. Nenhum outro validador cobre essas regras.

    if is_nfe:
        # Rule: DPREV_ENTREGA_FRETE — Rejeição 1157 preventiva
        # dPrevEntrega só é permitido em operações CIF. modFrete 1 (FOB) ou 9 rejeita.
        _frete_val = (mod_frete or {}).get("value", "")
        if d_prev_entrega and _frete_val in ("1", "9"):
            ev_id = "E_XML_DPREV_ENTREGA_FRETE"
            _add(
                Finding(
                    id="F_DPREV_ENTREGA_FRETE",
                    severity="FATAL",
                    rule_id="DPREV_ENTREGA_FRETE",
                    title=f"Rejeição 1157 — dPrevEntrega inválido para modFrete={_frete_val}",
                    where=FindingWhere(
                        field="dPrevEntrega",
                        xpath=_xpath("dPrevEntrega", doc_type),
                        snippet=d_prev_entrega["snippet"],
                    ),
                    recommendation=(
                        f"dPrevEntrega é permitido apenas em operações CIF. "
                        f"modFrete={_frete_val} ({'FOB' if _frete_val == '1' else 'Sem Frete'}) "
                        "causará Rejeição 1157 no SEFAZ. "
                        "Remova o campo ou altere a modalidade de frete (NT 2025.002 V1.36)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="dPrevEntrega — Rejeição 1157",
                         xpath=_xpath("dPrevEntrega", doc_type), snippet=d_prev_entrega["snippet"]),
            )

        # Rule: DPREV_ENTREGA_COMPETENCIA — divergência contabilização × apuração IBS
        # Quando dPrevEntrega está em mês/ano diferente do dhEmi:
        #   - Contabilização: mês da emissão (ICMS/legado)
        #   - Apuração IBS:   mês da entrega (dPrevEntrega)
        # Empresas fecham o mês sem o IBS correto sem este aviso.
        if d_prev_entrega and dh_emi:
            _dprev_month = d_prev_entrega["value"][:7]    # YYYY-MM
            _demi_month  = dh_emi["value"][:7]            # YYYY-MM (de YYYY-MM-DDTHH:...)
            if _dprev_month and _demi_month and _dprev_month != _demi_month:
                ev_id = "E_XML_DPREV_ENTREGA_COMPETENCIA"
                _add(
                    Finding(
                        id="F_DPREV_ENTREGA_COMPETENCIA",
                        severity="ALERT",
                        rule_id="DPREV_ENTREGA_COMPETENCIA",
                        title=(
                            f"Divergência de competência: IBS apurado em {_dprev_month}, "
                            f"contabilização em {_demi_month}"
                        ),
                        where=FindingWhere(
                            field="dPrevEntrega",
                            xpath=_xpath("dPrevEntrega", doc_type),
                            snippet=d_prev_entrega["snippet"],
                        ),
                        recommendation=(
                            f"dPrevEntrega ({_dprev_month}) difere do mês de emissão ({_demi_month}). "
                            "O débito de IBS será apurado em "
                            f"{_dprev_month} (mês da entrega), mas o ICMS e a contabilização "
                            f"ficam em {_demi_month} (mês da emissão). "
                            "Verifique a alíquota vigente na data de entrega e alinhe com o contador. "
                            "Use Evento 112150 se precisar corrigir a data de entrega após a emissão "
                            "(Cartilha CGIBS item 1.1 + 4.12)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="dPrevEntrega — divergência de competência",
                             xpath=_xpath("dPrevEntrega", doc_type), snippet=d_prev_entrega["snippet"]),
                )

        # Rule: DPREV_ENTREGA_CIF_AUSENTE — CIF sem dPrevEntrega
        # Em operações CIF, o fato gerador do IBS é a entrega, não a saída.
        # Sem dPrevEntrega, o IBS vai para o período de dhSaiEnt, que pode ser diferente da entrega.
        if not d_prev_entrega and _frete_val == "0":
            ev_id = "E_XML_DPREV_ENTREGA_CIF_AUSENTE"
            _add(
                Finding(
                    id="F_DPREV_ENTREGA_CIF_AUSENTE",
                    severity="ALERT",
                    rule_id="DPREV_ENTREGA_CIF_AUSENTE",
                    title="Operação CIF sem dPrevEntrega — risco de IBS em período incorreto",
                    where=FindingWhere(field="dPrevEntrega", xpath=_xpath("ide", doc_type)),
                    recommendation=(
                        "Operação CIF (frete por conta do emitente): o fato gerador do IBS ocorre "
                        "na entrega ao destinatário. Sem dPrevEntrega, o sistema de Apuração Assistida "
                        "do IBS usará a Data de Saída (dhSaiEnt). Se a entrega ocorrer em mês diferente "
                        "da saída, o IBS será lançado no período errado. "
                        "Preencha dPrevEntrega com a data prevista de entrega "
                        "ou use o Evento 112150 para corrigir após a emissão "
                        "(Cartilha CGIBS item 1.1 + NT 2025.002 V1.36)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="dPrevEntrega — ausente em CIF",
                         xpath=_xpath("ide", doc_type)),
            )

    # ── Rule 15: NCM_FORMAT ──────────────────────────────────────────────────

    if ncm:
        if not re.match(r"^\d{8}$", ncm["value"]):
            ev_id = "E_XML_NCM_FORMAT"
            _sev = _pedagogical_severity("NCM_FORMAT", pedagogical_mode)
            _rec = "NCM deve ter exatamente 8 dígitos conforme TIPI."
            if _sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_NCM_FORMAT", severity=_sev, rule_id="NCM_FORMAT", title=f'NCM inválido (esperado 8 dígitos, encontrado "{ncm["value"]}")', where=FindingWhere(field="NCM", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]), recommendation=_rec, evidence_ids=[ev_id]),
                Evidence(id=ev_id, type="xml", label="NCM — formato inválido", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]),
            )

    # ── Rule 16: NCM_VALID ─────────────────────────────────────────────────

    if ncm and re.match(r"^\d{8}$", ncm["value"]) and ncm["value"] not in VALID_NCM_CODES:
        ev_id = "E_XML_NCM_VALID"
        _sev = _pedagogical_severity("NCM_VALID", pedagogical_mode)
        _rec = "Verificar código NCM conforme Tabela TIPI vigente."
        if _sev == "WARNING":
            _rec += _LC227_RECOMMENDATION
        _add(
            Finding(id="F_NCM_VALID", severity=_sev, rule_id="NCM_VALID", title=f'NCM "{ncm["value"]}" não encontrado na tabela TIPI', where=FindingWhere(field="NCM", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]), recommendation=_rec, evidence_ids=[ev_id]),
            Evidence(id=ev_id, type="xml", label="NCM — código desconhecido", xpath=_xpath("NCM", doc_type), snippet=ncm["snippet"]),
        )

    # ── Rule 17: CLASSTRIB_VALID (enrichment — requires API pre-fetch) ─────

    if classtrib_results and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        code = c_class_trib["value"]
        lookup = classtrib_results.get(code)
        if lookup is False:
            ev_id = "E_XML_CLASSTRIB_VALID"
            _sev = _pedagogical_severity("CLASSTRIB_VALID", pedagogical_mode)
            _rec = "Verificar código cClassTrib no portal Conformidade Fácil (SVRS)."
            if _sev == "WARNING":
                _rec += _LC227_RECOMMENDATION
            _add(
                Finding(id="F_CLASSTRIB_VALID", severity=_sev, rule_id="CLASSTRIB_VALID", title=f'cClassTrib "{code}" não encontrado no registro SVRS', where=FindingWhere(field="cClassTrib", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]), recommendation=_rec, evidence_ids=[ev_id]),
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

    # ── Rule: CLASSTRIB_CST_COMPAT — cClassTrib compatível com o CST (Rejeição 1024) ──
    # CARRO-CHEFE: cada cClassTrib é registrado sob um CST específico (fonte oficial SVRS).
    # Se o CST declarado no grupo IBSCBS difere do CST do cClassTrib → incompatibilidade,
    # que a SEFAZ rejeita com a Rejeição 1024 (regra UB14-20). FATAL: é a rejeição dura que
    # o produto se propõe a prevenir; dado oficial e determinístico → alta confiança.
    if has_ibscbs and c_class_trib and cst and re.match(r"^\d{6}$", c_class_trib["value"]):
        _reg_cst = classtrib_cst(c_class_trib["value"])
        _decl_cst = cst["value"].strip()
        if _reg_cst and _decl_cst and _decl_cst != _reg_cst:
            ev_id = "E_XML_CLASSTRIB_CST_COMPAT"
            _add(
                Finding(
                    id="F_CLASSTRIB_CST_COMPAT", severity="FATAL", rule_id="CLASSTRIB_CST_COMPAT",
                    title=f'cClassTrib {c_class_trib["value"]} incompatível com o CST {_decl_cst} (esperado CST {_reg_cst})',
                    where=FindingWhere(field="cClassTrib", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
                    recommendation=(
                        f'O cClassTrib {c_class_trib["value"]} é registrado sob o CST {_reg_cst} (tabela oficial SVRS), '
                        f'mas a nota declarou o CST {_decl_cst}. Corrija o CST ou o cClassTrib. '
                        "SEFAZ: Rejeição 1024 (regra UB14-20 — cClassTrib incompatível com o CST informado)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cClassTrib × CST incompatível (Rejeição 1024)", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
            )

    # ── Rule: I08_191_CFOP_EXCLUSIVO_IBSCBS — RV I08-191 (NT 2026.007 v1.00, #615) ──
    # A avaliação vive em app/services/rules_i08_191.py, que separa DUAS perguntas
    # e nunca as colapsa: (A) o documento satisfaz as condições documentais e o
    # CFOP tem indExcIBSCBS=0? (B) há evidência de que a regra se aplica, isto é,
    # de que o autorizador é a SVRS?
    #
    # (B) NÃO é decidível a partir do XML e NÃO é inferida de cUF/UF — não existe
    # tabela canonizada UF→autorizador no produto. Por isso `autorizador` fica
    # None aqui: hoje ninguém no fluxo consegue comprovar SVRS, e o resultado é
    # sempre não-FATAL. Adquirir esse mapeamento como artefato versionado é gap
    # registrado, não improviso deste round.
    if doc_type == "NFE":
        from app.services import rules_i08_191 as _i08191

        _emit_block = _first_tag(xml, ["emit"])
        _mod_tag = _first_tag(xml, ["mod"])
        _i08191_res = _i08191.avaliar(_i08191.I08191Entrada(
            modelo=(_mod_tag or {}).get("value", "").strip(),
            emit_ie=(_first_tag(_emit_block["snippet"], ["IE"]) or {}).get("value") if _emit_block else None,
            cfops=[c["value"].strip() for c in _all_tags(xml, "CFOP")],
            fin_nfe=(_first_tag(xml, ["finNFe"]) or {}).get("value"),
            tp_nf_credito=(_first_tag(xml, ["tpNFCredito"]) or {}).get("value"),
            emissao=_parse_iso_date((emission_date or {}).get("value", "")),
            autorizador=None,
        ))
        if _i08191_res.severidade:
            ev_id = "E_XML_I08_191"
            _cfop_tag = next(
                (c for c in _all_tags(xml, "CFOP")
                 if c["value"].strip() == _i08191_res.cfop_nao_permitido), None)
            _add(
                Finding(
                    id="F_I08_191_CFOP_EXCLUSIVO_IBSCBS",
                    severity=_i08191_res.severidade,
                    rule_id="I08_191_CFOP_EXCLUSIVO_IBSCBS",
                    title=(
                        f"CFOP {_i08191_res.cfop_nao_permitido} não permitido ao contribuinte "
                        f"exclusivo do IBS/CBS — {_i08191_res.aplicabilidade}"
                    ),
                    where=FindingWhere(field="CFOP", xpath=_xpath("CFOP", doc_type),
                                       snippet=(_cfop_tag or {}).get("snippet", "")),
                    recommendation=_i08191.mensagem(_i08191_res),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml",
                         label=f"I08-191 — {_i08191_res.resultado} ({_i08191_res.aplicabilidade})",
                         xpath=_xpath("CFOP", doc_type),
                         snippet=(_cfop_tag or {}).get("snippet", "")),
            )

    # ── Rule: MONOFASICO_GRUPO_UB — subgrupo do UB84 presente quando exigido (NT v1.50, #404) ──
    # Checagem estrutural de presença do grupo XML exigido pelo indicador do cClassTrib
    # (fonte oficial SVRS). Não valida os valores de ad rem calculados dentro do grupo —
    # fora de escopo desta entrega, que cobre a obrigatoriedade estrutural confirmada.
    if has_ibscbs and ibscbs_block and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        _mono = classtrib_monofasico_grupos(c_class_trib["value"])
        if _mono:
            _mono_checks = [
                ("mono_retencao", "gMonoReten", "UB90-10"),
                ("mono_retido_anteriormente", "gMonoRet", "UB94-10"),
                ("mono_diferimento", "gMonoDif", "UB99-10"),
            ]
            _mono_em_date = emission_date["value"][:10] if emission_date else ""
            _mono_vigente = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", _mono_em_date)) and _mono_em_date >= _MONOFASICO_GRUPO_UB_DATE
            _mono_sev = "FATAL" if (_mono_vigente and not pedagogical_mode) else "WARNING"
            for _flag, _group, _validacao in _mono_checks:
                if _mono.get(_flag) and not _first_tag(ibscbs_block["snippet"], [_group]):
                    ev_id = f"E_XML_MONOFASICO_GRUPO_UB_{_group.upper()}"
                    _add(
                        Finding(
                            id=f"F_MONOFASICO_GRUPO_UB_{_group.upper()}", severity=_mono_sev, rule_id="MONOFASICO_GRUPO_UB",
                            title=f'cClassTrib {c_class_trib["value"]} exige o grupo {_group}, ausente na nota',
                            where=FindingWhere(field=_group, xpath=_xpath("IBSCBS", doc_type), snippet=c_class_trib["snippet"]),
                            recommendation=(
                                f'O cClassTrib {c_class_trib["value"]} tem o indicador correspondente ativo na tabela oficial SVRS '
                                f"(NT 2025.002 v1.50, regime monofásico de combustíveis) — o grupo {_group} é obrigatório e não "
                                f"foi encontrado na nota. SEFAZ: regra {_validacao}. Implantação em produção a partir de "
                                "04/01/2027 (antes disso, antecipação)."
                            ),
                            evidence_ids=[ev_id],
                        ),
                        Evidence(id=ev_id, type="xml", label=f"cClassTrib exige {_group} (regra {_validacao})", xpath=_xpath("IBSCBS", doc_type), snippet=c_class_trib["snippet"]),
                    )

    # ── Rule: MONOFASICO_AD_REM — valor ad rem confere com quantidade × alíquota (#478) ──
    # Complemento da MONOFASICO_GRUPO_UB, que só checava PRESENÇA do subgrupo. Aqui o
    # conteúdo é conferido: onde a tripla (quantidade, ad rem, valor) existir, o produto
    # tem de fechar. Independe de saber qual subgrupo é obrigatório — esse gap segue
    # aberto por falta de fonte, e esta regra não depende dele.
    if has_ibscbs and ibscbs_block:
        _ad_em_date = emission_date["value"][:10] if emission_date else ""
        _ad_vigente = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", _ad_em_date)) and _ad_em_date >= _MONOFASICO_GRUPO_UB_DATE
        _ad_sev = "FATAL" if (_ad_vigente and not pedagogical_mode) else "WARNING"
        for _q_tag, _ad_tag, _v_tag, _rotulo in _MONOFASICO_AD_REM_TRIPLAS:
            _q = _first_tag(ibscbs_block["snippet"], [_q_tag])
            _ad = _first_tag(ibscbs_block["snippet"], [_ad_tag])
            _v = _first_tag(ibscbs_block["snippet"], [_v_tag])
            if not (_q and _ad and _v):
                continue
            _qv, _adv, _vv = _to_float(_q["value"]), _to_float(_ad["value"]), _to_float(_v["value"])
            _esperado = _qv * _adv  # ad rem: R$/unidade — sem /100 (ver constante)
            if abs(_vv - _esperado) <= _MONOFASICO_AD_REM_TOL:
                continue
            ev_id = f"E_XML_MONOFASICO_AD_REM_{_v_tag.upper()}"
            _add(
                Finding(
                    id=f"F_MONOFASICO_AD_REM_{_v_tag.upper()}", severity=_ad_sev, rule_id="MONOFASICO_AD_REM",
                    title=f"{_rotulo} incorreto — R$ {_vv:.2f} vs esperado R$ {_esperado:.2f}",
                    where=FindingWhere(field=_v_tag, xpath=_xpath(_v_tag, doc_type), snippet=_v["snippet"]),
                    recommendation=(
                        f"No regime monofásico, {_v_tag} = {_q_tag} ({_qv:g}) × {_ad_tag} (R$ {_adv:g}) "
                        f"= R$ {_esperado:.2f}. A alíquota ad rem é um valor em reais POR UNIDADE, "
                        "não um percentual — não se divide por 100. Tolerância de R$ 0,01 "
                        "(NT 2025.002 v1.50, regime monofásico de combustíveis). Implantação em "
                        "produção a partir de 04/01/2027 (antes disso, antecipação)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label=f"{_rotulo} — cálculo ad rem divergente", xpath=_xpath(_v_tag, doc_type), snippet=_v["snippet"]),
            )

    # ── Rule 19: ALIQUOTA_CLASSTRIB — alíquota-zero coerente com o cClassTrib (#278) ──
    # Slice de alíquota-zero (independente das alíquotas de referência 2026, que ainda
    # têm ambiguidade — #315): se o cClassTrib é isento/imune (CST 400/410) ou tem
    # redução ≥ 100% (ex.: cesta básica), o IBS/CBS declarado DEVE ser 0. pCBS/pIBS > 0
    # nesse caso é FATAL. Dados da tabela oficial SVRS (classtrib.json, #328).
    # A comparação absoluta (alíquota não-zero vs esperada) fica para fase 2 (depende #315).
    if has_ibscbs and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        _exp = classtrib_expected_zero(c_class_trib["value"])
        if _exp is not None:
            _cbs_zero, _ibs_zero = _exp
            _TOL = 0.0001  # 0,01%
            _pcbs = _to_float(p_cbs["value"]) if p_cbs else 0.0
            _pibs_total = (
                (_to_float(p_ibs_uf["value"]) if p_ibs_uf else 0.0)
                + (_to_float(p_ibs_mun["value"]) if p_ibs_mun else 0.0)
            )
            if _cbs_zero and _pcbs > _TOL:
                ev_id = "E_XML_ALIQUOTA_CLASSTRIB_CBS"
                _add(
                    Finding(
                        id="F_ALIQUOTA_CLASSTRIB_CBS", severity="FATAL", rule_id="ALIQUOTA_CLASSTRIB",
                        title=f'cClassTrib {c_class_trib["value"]} é alíquota-zero de CBS, mas pCBS={_pcbs} foi declarado',
                        where=FindingWhere(field="pCBS", xpath=_xpath("pCBS", doc_type), snippet=p_cbs["snippet"] if p_cbs else None),
                        recommendation=(
                            f'O cClassTrib {c_class_trib["value"]} é isento/imune ou tem redução de 100% — '
                            "a CBS deve ser zero. Ajuste pCBS para 0 ou corrija o cClassTrib (tabela oficial SVRS)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="CBS — alíquota-zero incoerente", xpath=_xpath("pCBS", doc_type), snippet=p_cbs["snippet"] if p_cbs else None),
                )
            if _ibs_zero and _pibs_total > _TOL:
                ev_id = "E_XML_ALIQUOTA_CLASSTRIB_IBS"
                _add(
                    Finding(
                        id="F_ALIQUOTA_CLASSTRIB_IBS", severity="FATAL", rule_id="ALIQUOTA_CLASSTRIB",
                        title=f'cClassTrib {c_class_trib["value"]} é alíquota-zero de IBS, mas pIBSUF+pIBSMun={_pibs_total} foi declarado',
                        where=FindingWhere(field="pIBS", xpath=_xpath("pIBSUF", doc_type), snippet=p_ibs_uf["snippet"] if p_ibs_uf else None),
                        recommendation=(
                            f'O cClassTrib {c_class_trib["value"]} é isento/imune ou tem redução de 100% — '
                            "o IBS deve ser zero. Ajuste pIBSUF/pIBSMun para 0 ou corrija o cClassTrib (tabela oficial SVRS)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="IBS — alíquota-zero incoerente", xpath=_xpath("pIBSUF", doc_type), snippet=p_ibs_uf["snippet"] if p_ibs_uf else None),
                )

        # Fase 2 (#278): comparação ABSOLUTA — pCBS/pIBS vs referência 2026 × (1−redução).
        # ALERT advisory (não FATAL): há regimes monofásico/específico onde a derivação
        # ad-valorem não vale; não bloquear nota legítima (incerto → ALERT honesto). Só
        # emissão 2026 (a fase de transição 2027+ tem alíquotas em rampa — fora de escopo).
        _em2 = emission_date["value"][:10] if emission_date else ""
        if re.match(r"^2026-\d{2}-\d{2}$", _em2):
            _expa = classtrib_expected_aliquota_2026(c_class_trib["value"])
            if _expa is not None:
                _exp_cbs, _exp_ibs = _expa
                # Esperado e declarado estão ambos em PONTOS PERCENTUAIS (#617).
                _TOL2 = 0.01  # ±0,01 ponto percentual
                _pcbs2 = _to_float(p_cbs["value"]) if p_cbs else None
                _pibs2 = (
                    (_to_float(p_ibs_uf["value"]) if p_ibs_uf else 0.0)
                    + (_to_float(p_ibs_mun["value"]) if p_ibs_mun else 0.0)
                ) if (p_ibs_uf or p_ibs_mun) else None
                if _pcbs2 is not None and abs(_pcbs2 - _exp_cbs) > _TOL2:
                    ev_id = "E_XML_ALIQUOTA_CLASSTRIB_ABS_CBS"
                    _add(
                        Finding(
                            id="F_ALIQUOTA_CLASSTRIB_ABS_CBS", severity="ALERT", rule_id="ALIQUOTA_CLASSTRIB",
                            title=f'pCBS {_pcbs2} diverge do esperado ({round(_exp_cbs, 4)}) para o cClassTrib {c_class_trib["value"]} em 2026',
                            where=FindingWhere(field="pCBS", xpath=_xpath("pCBS", doc_type), snippet=p_cbs["snippet"] if p_cbs else None),
                            recommendation=(
                                f'Para o cClassTrib {c_class_trib["value"]}, a CBS esperada em 2026 é '
                                f'{round(_exp_cbs, 4)}% (0,9% × (1 − redução oficial SVRS)). Verifique a alíquota '
                                "declarada — exceto em regime monofásico/específico, onde a derivação não se aplica."
                            ),
                            evidence_ids=[ev_id],
                        ),
                        Evidence(id=ev_id, type="xml", label="CBS — alíquota diverge do cClassTrib (2026)", xpath=_xpath("pCBS", doc_type), snippet=p_cbs["snippet"] if p_cbs else None),
                    )
                if _pibs2 is not None and abs(_pibs2 - _exp_ibs) > _TOL2:
                    ev_id = "E_XML_ALIQUOTA_CLASSTRIB_ABS_IBS"
                    _add(
                        Finding(
                            id="F_ALIQUOTA_CLASSTRIB_ABS_IBS", severity="ALERT", rule_id="ALIQUOTA_CLASSTRIB",
                            title=f'pIBSUF+pIBSMun ({round(_pibs2, 6)}) diverge do esperado ({round(_exp_ibs, 4)}) para o cClassTrib {c_class_trib["value"]} em 2026',
                            where=FindingWhere(field="pIBS", xpath=_xpath("pIBSUF", doc_type), snippet=p_ibs_uf["snippet"] if p_ibs_uf else None),
                            recommendation=(
                                f'Para o cClassTrib {c_class_trib["value"]}, o IBS total esperado em 2026 é '
                                f'{round(_exp_ibs, 4)}% (0,1% × (1 − redução oficial SVRS)). Verifique a alíquota '
                                "declarada — exceto em regime monofásico/específico, onde a derivação não se aplica."
                            ),
                            evidence_ids=[ev_id],
                        ),
                        Evidence(id=ev_id, type="xml", label="IBS — alíquota diverge do cClassTrib (2026)", xpath=_xpath("pIBSUF", doc_type), snippet=p_ibs_uf["snippet"] if p_ibs_uf else None),
                    )

    # ── Rule 20: CRED_PRES — crédito presumido coerente com o cClassTrib (#339) ──
    # Fonte SVRS (IndPermiteCredPres): só alguns cClassTrib admitem crédito presumido.
    # Se o cClassTrib admite e a tag cCredPres não veio, a operação corre risco de rejeição
    # e PERDA do crédito (prejuízo direto). Severidade conservadora (janela 2026, educativa):
    # WARNING/ALERT, nunca FATAL — a geração efetiva do crédito depende de mais que o
    # cClassTrib (princípio: só FATAL com confiança; incerto → ALERT/fallback honesto).
    if has_ibscbs and ibscbs_block and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        _permite = classtrib_permite_cred_pres(c_class_trib["value"])
        _ccp = _first_tag(ibscbs_block["snippet"], ["cCredPres"])
        _ccp_val = _ccp["value"].strip() if _ccp and _ccp["value"] else ""
        if _permite is True and not _ccp_val:
            ev_id = "E_XML_CREDPRES_MISSING"
            _add(
                Finding(
                    id="F_CREDPRES_MISSING", severity="WARNING", rule_id="CRED_PRES",
                    title=f'cClassTrib {c_class_trib["value"]} admite crédito presumido, mas cCredPres não foi informado',
                    where=FindingWhere(field="cCredPres", xpath=_xpath("cCredPres", doc_type), snippet=c_class_trib["snippet"]),
                    recommendation=(
                        "Se a operação gera crédito presumido de IBS/CBS, informe o código cCredPres (6 dígitos) "
                        "no grupo IBSCBS. A ausência pode causar rejeição da NF-e e a perda do crédito (Tabela cCredPres, IT 2025.002)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cCredPres ausente — cClassTrib admite crédito presumido", xpath=_xpath("cCredPres", doc_type), snippet=c_class_trib["snippet"]),
            )
        elif _ccp_val and not re.match(r"^\d{6}$", _ccp_val):
            ev_id = "E_XML_CREDPRES_INVALID"
            _add(
                Finding(
                    id="F_CREDPRES_INVALID", severity="ALERT", rule_id="CRED_PRES",
                    title=f'cCredPres "{_ccp_val}" com formato inválido (esperado 6 dígitos)',
                    where=FindingWhere(field="cCredPres", xpath=_xpath("cCredPres", doc_type), snippet=_ccp["snippet"] if _ccp else None),
                    recommendation="O código de crédito presumido (cCredPres) deve ter 6 dígitos numéricos (Tabela cCredPres, IT 2025.002).",
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cCredPres — formato inválido", xpath=_xpath("cCredPres", doc_type), snippet=_ccp["snippet"] if _ccp else None),
            )
        elif _ccp_val and _permite is False:
            ev_id = "E_XML_CREDPRES_INCONSISTENT"
            _add(
                Finding(
                    id="F_CREDPRES_INCONSISTENT", severity="ALERT", rule_id="CRED_PRES",
                    title=f'cCredPres informado, mas o cClassTrib {c_class_trib["value"]} não admite crédito presumido',
                    where=FindingWhere(field="cCredPres", xpath=_xpath("cCredPres", doc_type), snippet=_ccp["snippet"] if _ccp else None),
                    recommendation="Reveja a classificação: este cClassTrib não admite crédito presumido (fonte SVRS). Verifique o cClassTrib ou remova o cCredPres.",
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cCredPres incoerente com cClassTrib", xpath=_xpath("cCredPres", doc_type), snippet=_ccp["snippet"] if _ccp else None),
            )

    # ── Rule 21: CLASSTRIB_DOC_TYPE — cClassTrib aplicável ao modelo do documento (#311) ──
    # Fonte SVRS (dfe_allowed): cada cClassTrib é publicado para modelos específicos
    # (NF-e/NFC-e/NFS-e/…). Usar um cClassTrib fora dos seus modelos tende à rejeição da
    # SEFAZ (cClassTrib inválido para o modelo — família 1106/960). Confiança alta na tabela,
    # mas o código de rejeição exato não é citável aqui → WARNING (não FATAL).
    # `classtrib_dfe_allowed` distingue DOIS estados que não podem voltar a colapsar:
    #   None → código desconhecido (outra regra trata; aqui nada a dizer)
    #   []   → código CONHECIDO que a fonte publica para NENHUM DFe
    # A condição anterior era `if _allowed and ...`: lista vazia é falsy, então os
    # 10 códigos desse segundo grupo passavam em SILÊNCIO em qualquer modelo (#680).
    #
    # Que [] significa mesmo "nenhum DFe" foi verificado contra a fonte em 26/08/2026:
    # nos 10 códigos as 14 chaves IndNfe/IndNfce/IndNfse/… estão TODAS PRESENTES e
    # TODAS false — declaração explícita, não ausência de informação. O controle
    # (000001) traz as mesmas 14 chaves com 11 verdadeiras.
    if doc_type and c_class_trib and re.match(r"^\d{6}$", c_class_trib["value"]):
        _allowed = classtrib_dfe_allowed(c_class_trib["value"])
        if _allowed is not None and doc_type not in _allowed:
            ev_id = "E_XML_CLASSTRIB_DOC_TYPE"
            _nenhum = not _allowed
            _modelos = ", ".join(_allowed)
            if _nenhum:
                _titulo = (
                    f'cClassTrib {c_class_trib["value"]} não é publicado para nenhum '
                    f"documento fiscal eletrônico"
                )
                _reco = (
                    f'O cClassTrib {c_class_trib["value"]} consta na tabela oficial SVRS, mas com '
                    "todos os indicadores de DFe negativos — não é aplicável a NF-e, NFC-e, NFS-e "
                    "nem aos demais modelos. Códigos assim existem para fluxos fora do DFe (a "
                    "importação, por exemplo, é declarada na DUIMP). Revise o cClassTrib do item."
                )
            else:
                _titulo = (
                    f'cClassTrib {c_class_trib["value"]} não é aplicável a {doc_type} '
                    f"(válido para: {_modelos})"
                )
                _reco = (
                    f'O cClassTrib {c_class_trib["value"]} é publicado apenas para {_modelos} (tabela oficial SVRS). '
                    f"Usá-lo em {doc_type} tende à rejeição da SEFAZ (cClassTrib inválido para o modelo — família 1106/960). "
                    "Revise o cClassTrib do item."
                )
            _add(
                Finding(
                    id="F_CLASSTRIB_DOC_TYPE", severity="WARNING", rule_id="CLASSTRIB_DOC_TYPE",
                    title=_titulo,
                    where=FindingWhere(field="cClassTrib", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
                    recommendation=_reco,
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cClassTrib — modelo de documento incompatível", xpath=_xpath("cClassTrib", doc_type), snippet=c_class_trib["snippet"]),
            )

    # ── Rule: IMPORT_IBSCBS_REQUIRED — incidência na importação (#item2) ──────
    # Decreto 12.955/2026 art. 65 (CBS) + Resolução CGIBS nº 6/2026 art. 65 (IBS)
    # — mesmo número de artigo nos dois regulamentos, publicados juntos em
    # 30/04/2026 (LC 214 art. 63): IBS/CBS incidem sobre a importação de bens e
    # serviços independentemente de o importador ser habitual. Detecção:
    # CFOP iniciando em "3" (entrada do exterior) OU grupo de importação (<DI>/<DUIMP>).
    # Export (CFOP 7xxx, imune) e internas ficam de fora. Escopo: grupo IBSCBS presente
    # porém zerado com CST tributável — grupo ausente já é coberto por IBSCBS_MISSING.
    if has_ibscbs and ibscbs_block:
        is_import = (
            any(c["value"].strip().startswith("3") for c in _all_tags(xml, "CFOP"))
            or re.search(r"<DI(?=[\s>])", xml, re.IGNORECASE) is not None
            or re.search(r"<DUIMP(?=[\s>])", xml, re.IGNORECASE) is not None
        )
        cst_value = cst["value"] if cst else ""
        v_cbs_num = _to_float(v_cbs["value"]) if v_cbs else 0.0
        v_ibs_num = _to_float(v_ibs["value"]) if v_ibs else 0.0
        if is_import and v_cbs_num + v_ibs_num == 0 and cst_value not in _NO_TAX_CSTS:
            ev_id = "E_XML_IMPORT_IBSCBS_REQUIRED"
            _add(
                Finding(
                    id="F_IMPORT_IBSCBS_REQUIRED", severity="FATAL", rule_id="IMPORT_IBSCBS_REQUIRED",
                    title="Importação tributável sem IBS/CBS destacado — incidência obrigatória",
                    where=FindingWhere(field="IBS/CBS", xpath=_xpath("IBSCBS", doc_type), snippet=ibscbs_block["snippet"]),
                    recommendation=(
                        f'Operação de importação (CFOP 3xxx ou grupo DI/DUIMP) com IBS/CBS zerado e '
                        f'CST {cst_value or "(ausente)"} tributável. O IBS e a CBS incidem sobre a importação '
                        f'de bens e serviços independentemente de o importador ser habitual '
                        f'(Decreto 12.955/2026 art. 65 para CBS + Resolução CGIBS nº 6/2026 art. 65 '
                        f'para IBS — mesmo artigo nos dois regulamentos; LC 214 art. 63). A alíquota deve corresponder à da '
                        f'operação interna com o mesmo bem/serviço (art. 469-470). Informe vCBS/vIBS ou ajuste o CST.'
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="Importação — IBS/CBS ausente", xpath=_xpath("IBSCBS", doc_type), snippet=ibscbs_block["snippet"]),
            )

    # ── Rule: PF_CONTRIB_CNPJ — PF contribuinte deve se inscrever no CNPJ (#item3) ──
    # Verificável do XML: emitente identificado por CPF, sem CNPJ, emissão ≥ 01/01/2027.
    # O ENQUADRAMENTO não é verificável do XML — nem como contribuinte, nem como
    # nanoempreendedor, nem como optante pelo regime regular. Por isso ALERT, nunca FATAL:
    # ausência de CNPJ não é irregularidade determinística.
    #
    # Ato Conjunto RFB/CGIBS nº 6/2026 (art. 2º) dispensa o nanoempreendedor do art. 25,
    # IV, dos Regulamentos CBS/IBS da inscrição no CNPJ e da emissão de DF-e, com efeitos
    # até 31/12/2028 (art. 3º). O parágrafo único exclui dessa dispensa quem exercer a
    # opção pelo regime regular do IBS e da CBS. Artefato canonizado em
    # app/data/regulatory_acts.json.
    #
    # A expiração em 31/12/2028 é FATO do ato, não gatilho: não autoriza concluir que em
    # 01/01/2029 a PF está obrigada ao CNPJ.
    em_date = emission_date["value"][:10] if emission_date else ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", em_date) and em_date >= _PF_CNPJ_REQUIRED_DATE:
        emit_block = _first_tag(xml, ["emit", "PrestadorServico", "prest", "Prestador"])
        if emit_block:
            emit_cpf = _first_tag(emit_block["snippet"], ["CPF"])
            emit_cnpj = _first_tag(emit_block["snippet"], ["CNPJ"])
            if emit_cpf and not emit_cnpj:
                ev_id = "E_XML_PF_CONTRIB_CNPJ"
                _add(
                    Finding(
                        id="F_PF_CONTRIB_CNPJ", severity="ALERT", rule_id="PF_CONTRIB_CNPJ",
                        title="Emitente pessoa física (CPF) — verificar obrigação de inscrição no CNPJ",
                        where=FindingWhere(field="emit/CPF", xpath=_xpath("CPF", doc_type), snippet=emit_cpf["snippet"]),
                        recommendation=(
                            "Emitente identificado por CPF, sem CNPJ. A partir de 1º/01/2027, a obrigação de inscrição no "
                            "CNPJ e de emissão de documentos fiscais passa a produzir efeitos para pessoas físicas que sejam "
                            "contribuintes ou responsáveis tributários da CBS, conforme o enquadramento aplicável. O Ato "
                            "Conjunto RFB/CGIBS nº 6/2026 dispensa o nanoempreendedor abrangido por suas regras, desde que "
                            "não exerça a opção pelo regime regular do IBS e da CBS, da obrigatoriedade de inscrição no CNPJ "
                            "e da emissão dos documentos fiscais eletrônicos nele abrangidos, com efeitos até 31/12/2028. "
                            "Este XML, isoladamente, não permite determinar se o emitente é contribuinte, nanoempreendedor "
                            "ou optante pelo regime regular. Verifique o enquadramento antes de concluir pela existência da "
                            "obrigação."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="Emitente PF (CPF) — verificar CNPJ", xpath=_xpath("CPF", doc_type), snippet=emit_cpf["snippet"]),
                )

    # ── Rule 22: DEVOLUCAO_DFEREF — devolução referencia a nota original por item (#312) ──
    # v1.40: NF-e de devolução (finNFe=4) deve referenciar a nota original POR ITEM,
    # exclusivamente via grupo DFeReferenciado. Antes de 01/09/2026 → WARNING (antecipação);
    # a partir da vigência → FATAL. pedagogical_mode mantém WARNING.
    if is_nfe:
        _fin = _first_tag(xml, ["finNFe"])
        if _fin and _fin["value"].strip() == "4":
            _n_items = len(re.findall(r"<det\b", xml))
            _n_ref = len(re.findall(r"<DFeReferenciado\b", xml))
            if _n_ref < max(_n_items, 1):
                _vigente = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", em_date)) and em_date >= _DEVOLUCAO_DFEREF_DATE
                _sev = "FATAL" if (_vigente and not pedagogical_mode) else "WARNING"
                _falta = "nenhum item referencia" if _n_ref == 0 else f"só {_n_ref} de {_n_items} itens referenciam"
                ev_id = "E_XML_DEVOLUCAO_DFEREF"
                _add(
                    Finding(
                        id="F_DEVOLUCAO_DFEREF", severity=_sev, rule_id="DEVOLUCAO_DFEREF",
                        title=f"NF-e de devolução sem DFeReferenciado por item ({_falta} a nota original)",
                        where=FindingWhere(field="DFeReferenciado", xpath=_xpath("DFeReferenciado", doc_type), snippet=_fin["snippet"]),
                        recommendation=(
                            "NF-e de devolução (finNFe=4) deve referenciar a nota original POR ITEM, "
                            "exclusivamente via grupo DFeReferenciado (NT 2025.002-RTC v1.40, vigência 01/09/2026). "
                            "Inclua um DFeReferenciado para cada item devolvido. SEFAZ: Rejeição 321 (regras VC02-14 / VC03-20)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="Devolução sem DFeReferenciado por item", xpath=_xpath("DFeReferenciado", doc_type), snippet=_fin["snippet"]),
                )

    # ── Rule 23: IS_CALC — coerência do Imposto Seletivo declarado (#314) ──────
    # vIS = vBCIS × pIS (ad valorem) + qTrib × pISEspec (específico). Incoerência → FATAL
    # (erro de cálculo é alta confiança). Tags exclusivas do IS (vIS/vBCIS/pIS), sem colisão
    # com o PIS legado (vPIS/pPIS). O IS só é cobrado a partir de 2027, mas a coerência do
    # grupo, quando declarado, é validável já.
    _is_match = re.search(r"<IS\b[^>]*>(.*?)</IS>", xml, re.DOTALL)
    if is_nfe and _is_match:
        _isblk = _is_match.group(1)

        def _isf(tag: str) -> float:
            t = _first_tag(_isblk, [tag])
            return _to_float(t["value"]) if t else 0.0

        _vis_tag = _first_tag(_isblk, ["vIS"])
        if _vis_tag:
            _expected_is = round(_isf("vBCIS") * _isf("pIS") + _isf("qTrib") * _isf("pISEspec"), 2)
            _vis_decl = _to_float(_vis_tag["value"])
            if abs(_vis_decl - _expected_is) > 0.01:
                ev_id = "E_XML_IS_CALC"
                _add(
                    Finding(
                        id="F_IS_CALC", severity="FATAL", rule_id="IS_CALC",
                        title=f"Imposto Seletivo incoerente: vIS={_vis_decl} declarado, esperado {_expected_is}",
                        where=FindingWhere(field="vIS", xpath=_xpath("vIS", doc_type), snippet=_vis_tag["snippet"]),
                        recommendation=(
                            "vIS deve ser vBCIS × pIS (ad valorem) + qTrib × pISEspec (específico), "
                            "conforme NT 2025.002-RTC. Ajuste a base, a alíquota ou o valor do IS."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="IS — cálculo incoerente", xpath=_xpath("vIS", doc_type), snippet=_vis_tag["snippet"]),
                )

    # ── Rule 24: IS_EXPECTED — NCM de capítulo sujeito ao IS sem grupo IS (#314) ──
    # Núcleo inequívoco do IS na LC 214: bebidas (cap. 22) e produtos fumígenos (cap. 24).
    # ALERT informativo (não FATAL): o IS só passa a ser cobrado em 2027 e há exceções.
    if is_nfe and ncm and re.match(r"^\d{8}$", ncm["value"]) and not _is_match:
        if ncm["value"][:2] in {"22", "24"}:
            ev_id = "E_XML_IS_EXPECTED"
            _add(
                Finding(
                    id="F_IS_EXPECTED", severity="ALERT", rule_id="IS_EXPECTED",
                    title=f'NCM {ncm["value"]} pode estar sujeito ao Imposto Seletivo — grupo IS ausente',
                    where=FindingWhere(field="IS", xpath=_xpath("IS", doc_type), snippet=ncm["snippet"]),
                    recommendation=(
                        "Produtos dos capítulos 22 (bebidas) e 24 (fumo) são, em regra, sujeitos ao "
                        "Imposto Seletivo (LC 214 art. 409). A cobrança do IS inicia em 2027; verifique "
                        "o enquadramento e, quando aplicável, informe o grupo IS na NF-e."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="IS — NCM possivelmente sujeito, grupo ausente", xpath=_xpath("IS", doc_type), snippet=ncm["snippet"]),
            )

    # ── Rule 25: SUFRAMA_DV — DV da Inscrição SUFRAMA do emitente (#311, C22-20) ──
    # WARNING (não FATAL): catch determinístico do DV, mas mantemos advisory para não
    # bloquear nota por nuance do algoritmo; cita o código oficial de rejeição.
    if is_nfe:
        _isuf = _first_tag(xml, ["ISUFemit", "ISUF"])
        if _isuf and _isuf["value"].strip() and not _suframa_dv_ok(_isuf["value"]):
            ev_id = "E_XML_SUFRAMA_DV"
            _add(
                Finding(
                    id="F_SUFRAMA_DV", severity="WARNING", rule_id="SUFRAMA_DV",
                    title=f'Inscrição SUFRAMA "{_isuf["value"].strip()}" — dígito verificador inválido',
                    where=FindingWhere(field="ISUFemit", xpath=_xpath("ISUFemit", doc_type), snippet=_isuf["snippet"]),
                    recommendation=(
                        "A Inscrição SUFRAMA do emitente deve ter 9 dígitos com DV válido (módulo 11). "
                        "Verifique a inscrição. SEFAZ: Rejeição C22-20 (DV da Inscrição SUFRAMA do emitente inválido)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="SUFRAMA — DV inválido", xpath=_xpath("ISUFemit", doc_type), snippet=_isuf["snippet"]),
            )

    # ── Rule 26: ALCZFM_NPROC — grupo gALCZFMCBS exige nProcSuframa (#311, UB66c-10) ──
    if is_nfe:
        _alc = re.search(r"<gALCZFMCBS\b[^>]*>([\s\S]*?)</gALCZFMCBS>", xml, re.IGNORECASE)
        if _alc:
            _nproc = _first_tag(_alc.group(1), ["nProcSuframa"])
            if not (_nproc and _nproc["value"].strip()):
                ev_id = "E_XML_ALCZFM_NPROC"
                _add(
                    Finding(
                        id="F_ALCZFM_NPROC", severity="WARNING", rule_id="ALCZFM_NPROC",
                        title="Grupo ALC/ZFM (gALCZFMCBS) sem nProcSuframa",
                        where=FindingWhere(field="nProcSuframa", xpath=_xpath("nProcSuframa", doc_type), snippet=_alc.group(0)[:200]),
                        recommendation=(
                            "Operações com benefício de ALC/Zona Franca (grupo gALCZFMCBS) exigem o número do "
                            "processo na SUFRAMA (nProcSuframa) do processo produtivo aprovado. Informe o nProcSuframa. "
                            "SEFAZ: Rejeição 1192 (regra UB66c-10 — número do processo na SUFRAMA não informado)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="ALC/ZFM — nProcSuframa ausente", xpath=_xpath("nProcSuframa", doc_type), snippet=_alc.group(0)[:200]),
                )

    # ── Rule 27: CINDOP_NFCE — cIndOp não é permitido na NFC-e (#311, B25d) ──
    # A NT v1.40 veda o campo cIndOp (Código Indicador do Local da Operação) no modelo 65.
    # Restrição explícita e determinística → regra limpa. WARNING (advisory, cita B25d).
    if doc_type == "NFCE":
        _cindop = _first_tag(xml, ["cIndOp"])
        if _cindop and _cindop["value"].strip():
            ev_id = "E_XML_CINDOP_NFCE"
            _add(
                Finding(
                    id="F_CINDOP_NFCE", severity="WARNING", rule_id="CINDOP_NFCE",
                    title="cIndOp informado em NFC-e (modelo 65) — não permitido",
                    where=FindingWhere(field="cIndOp", xpath=_xpath("cIndOp", doc_type), snippet=_cindop["snippet"]),
                    recommendation=(
                        "O campo cIndOp (Código Indicador do Local da Operação de Fornecimento) não é permitido "
                        "na NFC-e (modelo 65) — remova-o. SEFAZ: Rejeição 1099 (regra B25d-10)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="cIndOp — não permitido em NFC-e", xpath=_xpath("cIndOp", doc_type), snippet=_cindop["snippet"]),
            )

    # ── Rule 28: RETIRADA_CINDOP — B25d-30: cIndOp 010104/010105 exige Local de Retirada (#311) ──
    # Spec oficial (NT v1.40): se cIndOp = "010104" (leilão/licitação) ou "010105" (irregularidade)
    # e o grupo Local de Retirada (retirada/F01) não foi informado → Rejeição 1110. Modelo 55.
    if doc_type == "NFE":
        _cind = _first_tag(xml, ["cIndOp"])
        if _cind and _cind["value"].strip() in ("010104", "010105") and not re.search(r"<retirada(?=[\s>])", xml, re.IGNORECASE):
            ev_id = "E_XML_RETIRADA_CINDOP"
            _add(
                Finding(
                    id="F_RETIRADA_CINDOP", severity="WARNING", rule_id="RETIRADA_CINDOP",
                    title=f'cIndOp {_cind["value"].strip()} exige o grupo Local de Retirada (ausente)',
                    where=FindingWhere(field="retirada", xpath=_xpath("retirada", doc_type), snippet=_cind["snippet"]),
                    recommendation=(
                        "cIndOp 010104 (leilão/licitação) ou 010105 (irregularidade) exige o grupo Local de "
                        "Retirada (retirada) informado. SEFAZ: Rejeição 1110 (regra B25d-30)."
                    ),
                    evidence_ids=[ev_id],
                ),
                Evidence(id=ev_id, type="xml", label="Local de Retirada ausente (cIndOp 010104/010105)", xpath=_xpath("retirada", doc_type), snippet=_cind["snippet"]),
            )

    # ── Rule 29: ALCZFM_CBS_CALC — UB66e-10: vTribRegCBS = vBC × pAliqEfetRegCBS/100 (#311) ──
    # Spec oficial (Rejeição 1218): coerência do valor da CBS na operação ALC/ZFM. WARNING.
    _alc2 = re.search(r"<gALCZFMCBS\b[^>]*>([\s\S]*?)</gALCZFMCBS>", xml, re.IGNORECASE)
    if is_nfe and _alc2:
        _blk = _alc2.group(1)
        _vtrib = _first_tag(_blk, ["vTribRegCBS"])
        _palq = _first_tag(_blk, ["pAliqEfetRegCBS"])
        _vbc_t = _first_tag(xml, ["vBC"])
        if _vtrib and _palq and _vbc_t:
            _exp = round(_to_float(_vbc_t["value"]) * _to_float(_palq["value"]) / 100, 2)
            _decl = _to_float(_vtrib["value"])
            if abs(_decl - _exp) > 0.01:
                ev_id = "E_XML_ALCZFM_CBS_CALC"
                _add(
                    Finding(
                        id="F_ALCZFM_CBS_CALC", severity="WARNING", rule_id="ALCZFM_CBS_CALC",
                        title=f"vTribRegCBS ({_decl}) diverge do calculado ({_exp}) na operação ALC/ZFM",
                        where=FindingWhere(field="vTribRegCBS", xpath=_xpath("vTribRegCBS", doc_type), snippet=_vtrib["snippet"]),
                        recommendation=(
                            "Em operação ALC/ZFM, vTribRegCBS deve ser vBC × (pAliqEfetRegCBS / 100). "
                            "Ajuste o valor. SEFAZ: Rejeição 1218 (regra UB66e-10)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="ALC/ZFM — vTribRegCBS incoerente", xpath=_xpath("vTribRegCBS", doc_type), snippet=_vtrib["snippet"]),
                )

    # ── Rule: DANFE_SIMPLIFICADO_RESTRICAO — restrições do DANFE Simplificado Tipo 2 (NT 2026.002 v1.00, #405) ──
    # tpImp=6 (modelo 55 apenas — Ajuste SINIEF 13/2026) restringe a nota a: saída
    # (tpNF≠0), operação interna (idDest=1), sem NFref e finalidade Normal (finNFe=1).
    # 4 restrições confirmadas com código de rejeição oficial e convergência de fontes
    # independentes. Allowlist de CFOP (5ª restrição) coberta por DANFE_SIMPLIFICADO_CFOP,
    # abaixo (#482). Fora de escopo: o grupo de alerta cStat=120/PR13 (vive no protocolo
    # de autorização da SEFAZ, não no XML emitido — fora do que este validador processa).
    if doc_type == "NFE":
        _tp_imp = _first_tag(xml, ["tpImp"])
        if _tp_imp and _tp_imp["value"].strip() == "6":
            _t2_em_date = emission_date["value"][:10] if emission_date else ""
            _t2_vigente = bool(re.match(r"^\d{4}-\d{2}-\d{2}$", _t2_em_date)) and _t2_em_date >= _DANFE_T2_PRODUCAO_DATE
            _t2_sev = "FATAL" if (_t2_vigente and not pedagogical_mode) else "WARNING"

            _tp_nf = _first_tag(xml, ["tpNF"])
            if _tp_nf and _tp_nf["value"].strip() == "0":
                ev_id = "E_XML_DANFE_T2_ENTRADA"
                _add(
                    Finding(
                        id="F_DANFE_T2_ENTRADA", severity=_t2_sev, rule_id="DANFE_SIMPLIFICADO_RESTRICAO",
                        title="DANFE Simplificado Tipo 2 (tpImp=6) não é admitido em operação de entrada (tpNF=0)",
                        where=FindingWhere(field="tpNF", xpath=_xpath("tpNF", doc_type), snippet=_tp_nf["snippet"]),
                        recommendation=(
                            "O DANFE Simplificado Tipo 2 (Ajuste SINIEF 13/2026) só é admitido em operações de "
                            "saída. Corrija tpNF ou remova tpImp=6. SEFAZ: Rejeição 706 (regra B11-10)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="DANFE T2 — operação de entrada não permitida", xpath=_xpath("tpNF", doc_type), snippet=_tp_nf["snippet"]),
                )

            _id_dest = _first_tag(xml, ["idDest"])
            if _id_dest and _id_dest["value"].strip() != "1":
                ev_id = "E_XML_DANFE_T2_INTERESTADUAL"
                _add(
                    Finding(
                        id="F_DANFE_T2_INTERESTADUAL", severity=_t2_sev, rule_id="DANFE_SIMPLIFICADO_RESTRICAO",
                        title="DANFE Simplificado Tipo 2 (tpImp=6) não é admitido em operação interestadual/exterior (idDest≠1)",
                        where=FindingWhere(field="idDest", xpath=_xpath("idDest", doc_type), snippet=_id_dest["snippet"]),
                        recommendation=(
                            "O DANFE Simplificado Tipo 2 só é admitido em operações internas (idDest=1). "
                            "Corrija idDest ou remova tpImp=6. SEFAZ: Rejeição 707 (regra B11a-10)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="DANFE T2 — operação interestadual/exterior não permitida", xpath=_xpath("idDest", doc_type), snippet=_id_dest["snippet"]),
                )

            if re.search(r"<NFref(?=[\s>])", xml, re.IGNORECASE):
                ev_id = "E_XML_DANFE_T2_NFREF"
                _add(
                    Finding(
                        id="F_DANFE_T2_NFREF", severity=_t2_sev, rule_id="DANFE_SIMPLIFICADO_RESTRICAO",
                        title="DANFE Simplificado Tipo 2 (tpImp=6) não pode referenciar outro documento fiscal (NFref)",
                        where=FindingWhere(field="NFref", xpath=_xpath("NFref", doc_type), snippet=_tp_imp["snippet"]),
                        recommendation=(
                            "O DANFE Simplificado Tipo 2 não admite o grupo NFref (referência a outro documento "
                            "fiscal). Remova o NFref ou o tpImp=6. SEFAZ: Rejeição 708 (regra BA01-10)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="DANFE T2 — referência a documento fiscal não permitida", xpath=_xpath("NFref", doc_type), snippet=_tp_imp["snippet"]),
                )

            _fin_t2 = _first_tag(xml, ["finNFe"])
            if _fin_t2 and _fin_t2["value"].strip() != "1":
                ev_id = "E_XML_DANFE_T2_FINALIDADE"
                _add(
                    Finding(
                        id="F_DANFE_T2_FINALIDADE", severity=_t2_sev, rule_id="DANFE_SIMPLIFICADO_RESTRICAO",
                        title="DANFE Simplificado Tipo 2 (tpImp=6) exige finalidade Normal (finNFe=1)",
                        where=FindingWhere(field="finNFe", xpath=_xpath("finNFe", doc_type), snippet=_fin_t2["snippet"]),
                        recommendation=(
                            "O DANFE Simplificado Tipo 2 só é admitido com finalidade Normal (finNFe=1). "
                            "Corrija finNFe ou remova tpImp=6. SEFAZ: Rejeição 715 (regra B25-20)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="DANFE T2 — finalidade não permitida", xpath=_xpath("finNFe", doc_type), snippet=_fin_t2["snippet"]),
                )

            # ── Rule: DANFE_SIMPLIFICADO_CFOP — allowlist de CFOP (NT 2026.002 v1.00, #482) ──
            # Regra I08-150 — Rejeição 725 (mesmo código já usado pela SEFAZ para "NFC-e com
            # CFOP inválido", reaproveitado para NF-e+tpImp=6 — DANFE Simplificado Tipo 2
            # estende a mesma semântica de venda direta ao consumidor da NFC-e ao NF-e mod. 55).
            # Confirmado por 2 fontes independentes (fórum SPED Brasil + doc. Senior listando
            # I08-150 entre as regras da NT 2026.002 v1.00) + a lista de CFOPs bate quase 1:1
            # com a lista já documentada da Rejeição 725 de NFC-e (mesma fonte, +1 código: 5910).
            _cfop_allowlist = {"5101", "5102", "5103", "5104", "5115", "5405", "5656", "5667", "5910", "5933"}
            _bad_cfop = next((c for c in _all_tags(xml, "CFOP") if c["value"].strip() not in _cfop_allowlist), None)
            if _bad_cfop:
                ev_id = "E_XML_DANFE_T2_CFOP"
                _add(
                    Finding(
                        id="F_DANFE_T2_CFOP", severity=_t2_sev, rule_id="DANFE_SIMPLIFICADO_CFOP",
                        title=f"DANFE Simplificado Tipo 2 (tpImp=6) não admite CFOP {_bad_cfop['value']} — fora do allowlist de venda direta ao consumidor",
                        where=FindingWhere(field="CFOP", xpath=_xpath("CFOP", doc_type), snippet=_bad_cfop["snippet"]),
                        recommendation=(
                            "O DANFE Simplificado Tipo 2 só admite CFOPs de venda direta ao consumidor: 5101, "
                            "5102, 5103, 5104, 5115, 5405, 5656, 5667, 5910, 5933. Corrija o CFOP do item ou "
                            "remova tpImp=6. SEFAZ: Rejeição 725 (regra I08-150)."
                        ),
                        evidence_ids=[ev_id],
                    ),
                    Evidence(id=ev_id, type="xml", label="DANFE T2 — CFOP fora do allowlist", xpath=_xpath("CFOP", doc_type), snippet=_bad_cfop["snippet"]),
                )

    # ── NT v1.40 — anotar código de rejeição SEFAZ nas detecções (#311) ───────
    # Apenas NF-e/NFC-e (rejeições da SEFAZ NF-e; NFS-e tem regras próprias).
    if is_nfe:
        for f in findings:
            code = _REJECTION_CODES.get(f.rule_id)
            if code:
                f.recommendation = (f.recommendation or "") + code

    # ── Janela sem penalidades (Ato Conjunto RFB/CGIBS 1/25) — passe final ────
    # Downgrade automático FATAL → WARNING das obrigações acessórias quando a
    # nota cai na janela (por dhEmi). O pedagogical_mode (LC 227) já foi aplicado
    # inline acima; esta passada cobre o caso automático por data.
    if _within_no_penalty_window(emission_date):
        for f in findings:
            if f.severity == "FATAL" and f.rule_id in _PEDAGOGICAL_ACCESSORY_RULES:
                f.severity = "WARNING"
                f.recommendation = (f.recommendation or "") + _ATO_CONJUNTO_RECOMMENDATION

    fatals = sum(1 for f in findings if f.severity == "FATAL")
    alerts = sum(1 for f in findings if f.severity in ("ALERT", "WARNING"))
    regime_comparison = _extract_regime_comparison(xml, has_ibscbs)

    return ValidationResult(
        job_id=job_id,
        audit_id=audit_id,
        document_type=doc_type,
        findings=findings,
        evidences=evidences,
        fatals=fatals,
        alerts=alerts,
        created_at=datetime.now(timezone.utc).isoformat(),
        regime_comparison=regime_comparison,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post(
    "/validate/xml",
    response_model=ValidationResult,
    dependencies=[
        Depends(require_plan("trial", "starter", "profissional", "contador")),
        Depends(check_usage_limit("validations")),
    ],
)
async def validate_xml_endpoint(
    file: UploadFile = File(None),
    xml_content: str = Form(None),
    document_type: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
        raise HTTPException(status_code=400, detail="Envie um arquivo XML ou xml_content.")

    doc_type = document_type if document_type in ("NFSE", "NFE", "NFCE") else None

    # Async enrichment: ClassTrib + CNPJ lookups
    classtrib_data = await _enrich_classtrib(xml)
    cnpj_data = await _enrich_cnpj(xml)

    # Lê flag pedagógico do tenant
    from app.models.auth import Tenant
    tenant = db.get(Tenant, current_user.tenant_id)
    pedagogical = bool(tenant.pedagogical_mode_2026) if tenant else True

    result = validate_xml(
        xml, doc_type,
        classtrib_results=classtrib_data,
        cnpj_result=cnpj_data,
        pedagogical_mode=pedagogical,
    )

    tenant_id = str(current_user.tenant_id)
    user_id = str(current_user.id)

    # Persist job record — id explícito garante que result.job_id == row.id no banco
    try:
        sp = db.begin_nested()
        job_result: dict[str, Any] = {
            "fatals": result.fatals,
            "alerts": result.alerts,
            "findings_count": len(result.findings),
            "findings": [f.model_dump() for f in result.findings],
        }
        if result.regime_comparison:
            job_result["regime_comparison"] = result.regime_comparison.model_dump()
        db.add(JobModel(
            id=UUID(result.job_id),
            tenant_id=current_user.tenant_id,
            job_type="validate_xml",
            status="SUCCESS",
            payload={"document_type": result.document_type, "audit_id": result.audit_id},
            result=job_result,
        ))
        sp.commit()
    except Exception:
        logger.warning("validate_xml: failed to persist job record", exc_info=True)
        sp.rollback()

    postgres_tool.insert_audit_log(
        tenant_id=tenant_id,
        user_id=user_id,
        action="xml_validation_fail" if result.fatals > 0 else "xml_validation_pass",
        entity_type="xml_document",
        entity_id=result.job_id,
        payload={
            "document_type": result.document_type,
            "findings_count": len(result.findings),
            "fatals": result.fatals,
            "alerts": result.alerts,
            "audit_id": result.audit_id,
        },
    )

    increment_usage(db, current_user, "validations")
    db.commit()


    return result


# ── XML Correction (MVP) ───────────────────────────────────────────────────

class CorrectionResponse(BaseModel):
    document_id: str
    storage_key: str
    download_url: str
    applied_corrections: list[str]
    unresolved_findings: list[dict]
    created_at: str


@router.post(
    "/validate/xml/correct",
    response_model=CorrectionResponse,
    dependencies=[
        Depends(require_plan("trial", "starter", "profissional", "contador")),
        Depends(check_usage_limit("validations")),
    ],
)
async def correct_xml_endpoint(
    file: UploadFile = File(None),
    xml_content: str = Form(None),
    document_type: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CorrectionResponse:
    """Generate and persist a corrected XML (MVP normalization only).

    - Normalizes XML (whitespace) deterministically
    - Reuses validator to collect findings and mark them unresolved
    - Persists corrected XML as a Document (doc_type='other', artifact_kind='corrected_xml')
    - Returns presigned download URL
    """
    if file:
        raw = await file.read()
        xml = raw.decode("utf-8")
    elif xml_content:
        xml = xml_content
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo XML ou xml_content.")

    # Determine document type similar to validation endpoint
    doc_type = document_type if document_type in ("NFSE", "NFE", "NFCE") else None

    # Re-run validator to capture findings to feed correction summary
    validation = validate_xml(xml, doc_type)

    # Apply correction (MVP)
    corrected_xml, summary = correct_xml(
        xml=xml,
        document_type=doc_type,
        findings=[
            {
                "id": f.id,
                "rule_id": f.rule_id,
                "severity": f.severity,
                "title": f.title,
            }
            for f in validation.findings
        ],
    )

    # Persist corrected file as Document (doc_type='other' with artifact_kind)
    key = f"documents/{current_user.tenant_id}/corrected_xml/{uuid4()}.xml"
    put = s3_tool.put_object(
        key=key,
        data=corrected_xml.encode("utf-8"),
        content_type="application/xml",
        metadata={
            "artifact_kind": "corrected_xml",
            "source": "validate_xml.correct",
        },
    )

    doc = Document(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        doc_type="other",
        original_filename=None,
        storage_key=key,
        content_type="application/xml",
        status="confirmed",
        uploaded_at=datetime.now(timezone.utc),
        fiscal_metadata={
            "artifact_kind": "corrected_xml",
            "corrected_checksum": put.get("checksum_sha256", ""),
            "applied_corrections": summary.applied_corrections,
            "unresolved_findings": summary.unresolved_findings,
            "document_type": doc_type or validation.document_type,
            "source_job_id": validation.job_id,
        },
    )
    db.add(doc)
    increment_usage(db, current_user, "validations")
    db.commit()
    db.refresh(doc)

    # Audit artifact
    postgres_tool.persist_artifact_metadata(
        tenant_id=str(current_user.tenant_id),
        entity_type="document",
        entity_id=str(doc.id),
        artifact_type="corrected_xml",
        storage_key=key,
        checksum=put.get("checksum_sha256", ""),
        metadata={"source": "validate_xml.correct"},
    )

    # Presigned download URL
    url = s3_tool.get_object_url(key=key)

    # Sanitize unresolved findings for response (id, rule_id, severity only)
    safe_unresolved = [
        {k: v for k, v in f.items() if k in ("id", "rule_id", "severity")}
        for f in (summary.unresolved_findings or [])
        if isinstance(f, dict)
    ]

    return CorrectionResponse(
        document_id=str(doc.id),
        storage_key=key,
        download_url=url,
        applied_corrections=summary.applied_corrections,
        unresolved_findings=safe_unresolved,
        created_at=datetime.now(timezone.utc).isoformat(),
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
    from app.services.cnpj_validator import is_valid_cnpj_format
    from app.services.cnpj_validator import validate_cnpj as _validate_cnpj

    # Extract emitter CNPJ (first CNPJ in emit block, or first CNPJ in document)
    emit_block = _first_tag(xml, ["emit", "PrestadorServico"])
    if not emit_block:
        return None
    cnpj_tag = _first_tag(emit_block["snippet"], ["CNPJ"])
    if not cnpj_tag or not is_valid_cnpj_format(cnpj_tag["value"]):
        return None
    try:
        result = await _validate_cnpj(cnpj_tag["value"])
        return (result.valid and result.status == "ATIVA", result.status)
    except Exception:
        return None
