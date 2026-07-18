"""Tabela cClassTrib (6 dígitos) carregada de classtrib.json — fonte oficial SVRS (#313/#328).

Usada pela regra ALIQUOTA_CLASSTRIB (#278) para o slice de alíquota-zero: determinar,
de forma independente das alíquotas de referência, se um cClassTrib deve ter IBS/CBS = 0.

Um cClassTrib é "alíquota-zero" para um tributo quando:
  - o CST é 400 (isenção) ou 410 (imunidade/não incidência), OU
  - a redução daquele tributo é >= 100% (ex.: cesta básica).
"""

from __future__ import annotations

import json
from pathlib import Path

from app.data.uf_rates import (
    CBS_NATIONAL_RATE,
    CBS_TESTE_2026,
    IBS_NATIONAL_RATE,
    IBS_TESTE_2026_TOTAL,
)

_DATA = json.loads((Path(__file__).parent / "classtrib.json").read_text(encoding="utf-8"))
CLASSTRIB_BY_CODE: dict[str, dict] = _DATA.get("by_code", {})
# Data da última sincronização SVRS (bloco meta) — exposto como last_synced_at na API.
CLASSTRIB_SYNCED_AT: str | None = _DATA.get("meta", {}).get("date")

# CSTs do cClassTrib que zeram o tributo independentemente de redução.
_ZERO_CSTS = {"400", "410"}

# Alíquotas de referência em pontos percentuais (uf_rates guarda como fração).
_CBS_PLENA = float(CBS_NATIONAL_RATE) * 100  # 8,8
_IBS_PLENA = float(IBS_NATIONAL_RATE) * 100  # 17,7
_CBS_2026 = float(CBS_TESTE_2026) * 100      # 0,9
_IBS_2026 = float(IBS_TESTE_2026_TOTAL) * 100  # 0,1


def classtrib_expected_zero(code: str) -> tuple[bool, bool] | None:
    """Retorna (cbs_zero, ibs_zero) para o cClassTrib, ou None se o código for desconhecido.

    cbs_zero/ibs_zero = True quando aquele tributo deve ser 0% para este cClassTrib.
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    cst = str(item.get("cst", ""))
    is_exempt = cst in _ZERO_CSTS
    cbs_zero = is_exempt or float(item.get("reduction_cbs_pct", 0) or 0) >= 100
    ibs_zero = is_exempt or float(item.get("reduction_ibs_pct", 0) or 0) >= 100
    return cbs_zero, ibs_zero


def classtrib_permite_cred_pres(code: str) -> bool | None:
    """Indica se o cClassTrib permite crédito presumido (tag cCredPres) — #339.

    Retorna True/False (fonte SVRS: IndPermiteCredPres) ou None se o código for desconhecido.
    Apenas alguns cClassTrib permitem; quando permitem, a ausência de cCredPres na operação
    pode levar à rejeição da NF-e e à perda do crédito.
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    return bool(item.get("permite_cred_pres", False))


def classtrib_dfe_allowed(code: str) -> list[str] | None:
    """Modelos de DFe em que o cClassTrib é aplicável (ex.: ['NFE','NFCE']) — #311.

    Retorna a lista (fonte SVRS: IndNfe/IndNfce/IndNfse/…) ou None se o código for
    desconhecido. Usar um cClassTrib fora dos seus modelos publicados tende à rejeição
    (cClassTrib inválido para o modelo — família 1106/960).
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    return list(item.get("dfe_allowed") or [])


def classtrib_expected_aliquota_2026(code: str) -> tuple[float, float] | None:
    """(pCBS, pIBS_total) esperados para o cClassTrib na fase de teste 2026 — #278 fase 2.

    Deriva da redução oficial × alíquota de referência de 2026 (CBS 0,9% / IBS 0,1%, #315):
        esperado = base × (1 − redução/100).
    Retorna None para códigos zero-rate (cobertos pela fase 1, que é FATAL) ou desconhecidos.
    Nota: para regimes monofásico/específico a derivação ad-valorem não se aplica — por isso
    a regra fase 2 emite ALERT (advisory), nunca FATAL.
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    cst = str(item.get("cst", ""))
    red_cbs = float(item.get("reduction_cbs_pct", 0) or 0)
    red_ibs = float(item.get("reduction_ibs_pct", 0) or 0)
    if cst in _ZERO_CSTS or red_cbs >= 100 or red_ibs >= 100:
        return None
    exp_cbs = float(CBS_TESTE_2026) * (1 - red_cbs / 100)
    exp_ibs = float(IBS_TESTE_2026_TOTAL) * (1 - red_ibs / 100)
    return round(exp_cbs, 6), round(exp_ibs, 6)


def classtrib_monofasico_grupos(code: str) -> dict[str, bool] | None:
    """Indica quais subgrupos do UB84 (gIBSCBSMono) o cClassTrib exige — NT 2025.002 v1.50, #404.

    Fonte SVRS: IndMonoRetem (gMonoReten — sujeita à retenção, UB90), IndMonoRet
    (gMonoRet — retida anteriormente, UB94), IndMonoDif (gMonoDif — diferimento,
    UB99). Retorna None se o código for desconhecido, ou um dict sempre com as
    três chaves (False quando o cClassTrib não exige aquele subgrupo).

    Confirmado nesta entrega: o schema real não expõe indicador equivalente para
    gMonoPadrao (UB84a) — parece ser o caso default quando nenhum dos três acima
    se aplica. Essa checagem específica fica fora de escopo por falta de
    confirmação 1:1 do gatilho oficial; não implementada para evitar regra
    especulativa.
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    return {
        "mono_retencao": bool(item.get("mono_retencao", False)),
        "mono_retido_anteriormente": bool(item.get("mono_retido_anteriormente", False)),
        "mono_diferimento": bool(item.get("mono_diferimento", False)),
    }


def classtrib_cst(code: str) -> str | None:
    """CST oficial registrado para o cClassTrib (fonte SVRS) — usado na Rejeição 1024.

    Cada cClassTrib pertence a exatamente um CST. Retorna o CST registrado, ou None se o
    código for desconhecido. Permite validar a compatibilidade cClassTrib × CST (UB14-20).
    """
    item = CLASSTRIB_BY_CODE.get(code)
    if item is None:
        return None
    return str(item.get("cst", "")) or None


def _regime_slug(cst: str, red_cbs: float, red_ibs: float) -> str:
    """Rótulo de regime derivado (padrao/isencao/imunidade/reducao_integral/reducao_N).

    Mesma lógica que populou cclass_trib_items na migration 0020 — agora servida
    direto do JSON (fonte única, #365).
    """
    if cst == "400":
        return "isencao"
    if cst == "410":
        return "imunidade"
    r = max(red_cbs, red_ibs)
    if r >= 100:
        return "reducao_integral"
    if r > 0:
        return f"reducao_{int(r)}"
    return "padrao"


def classtrib_api_item(code: str) -> dict | None:
    """cClassTrib no formato do endpoint público, derivado do classtrib.json (#365).

    Substitui a leitura da tabela DB `cclass_trib_items` — assim a API pública e o motor
    compartilham a MESMA fonte, e o re-sync diário mantém ambos frescos sem migration.
    Alíquotas em pontos percentuais: p_cbs/p_ibs = referência PLENA (8,8/17,7); os campos
    *_2026 = fase de teste de 2026 (0,9/0,1). Isenção (CST 400)/imunidade (410) → 0.
    """
    it = CLASSTRIB_BY_CODE.get(code)
    if it is None:
        return None
    cst = str(it.get("cst", ""))
    red_cbs = float(it.get("reduction_cbs_pct", 0) or 0)
    red_ibs = float(it.get("reduction_ibs_pct", 0) or 0)
    zero = cst in _ZERO_CSTS
    return {
        "codigo": code,
        "descricao": (it.get("description") or "").strip() or code,
        "p_cbs": 0.0 if zero else round(_CBS_PLENA * (1 - red_cbs / 100), 4),
        "p_ibs": 0.0 if zero else round(_IBS_PLENA * (1 - red_ibs / 100), 4),
        "p_cbs_2026": 0.0 if zero else round(_CBS_2026 * (1 - red_cbs / 100), 4),
        "p_ibs_2026": 0.0 if zero else round(_IBS_2026 * (1 - red_ibs / 100), 4),
        "regime_especial": _regime_slug(cst, red_cbs, red_ibs),
        "vigencia_ini": (it.get("vigencia_ini") or "2026-01-01") or "2026-01-01",
        "vigencia_fim": None,
        "is_active": True,
        "last_synced_at": CLASSTRIB_SYNCED_AT,
    }


def classtrib_api_search(q: str, limit: int) -> list[dict]:
    """Busca por substring na descrição (case-insensitive), ordenada por descrição (#365)."""
    ql = q.lower()
    hits = [
        classtrib_api_item(code)
        for code, it in CLASSTRIB_BY_CODE.items()
        if ql in (it.get("description") or "").lower()
    ]
    hits.sort(key=lambda r: r["descricao"] if r else "")
    return [h for h in hits if h][:limit]
