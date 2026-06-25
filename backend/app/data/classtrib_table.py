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

from app.data.uf_rates import CBS_TESTE_2026, IBS_TESTE_2026_TOTAL

_DATA = json.loads((Path(__file__).parent / "classtrib.json").read_text(encoding="utf-8"))
CLASSTRIB_BY_CODE: dict[str, dict] = _DATA.get("by_code", {})

# CSTs do cClassTrib que zeram o tributo independentemente de redução.
_ZERO_CSTS = {"400", "410"}


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
