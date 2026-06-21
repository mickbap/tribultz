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
