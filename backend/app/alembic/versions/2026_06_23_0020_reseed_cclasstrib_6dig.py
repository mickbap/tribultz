"""reseed_cclasstrib_6dig — Part 2 do #313

Re-seed de cclass_trib_items com os 156 cClassTrib de 6 dígitos (app/data/classtrib.json,
fonte pública SVRS / NT 2025.002-RTC v1.40), substituindo a taxonomia de produto antiga
(formato "01.01.001", da migration 0018). A partir daqui o /classtrib/{codigo} e o
validate_classtrib operam sobre o cClassTrib real da NF-e.

p_cbs/p_ibs = redução × alíquota de REFERÊNCIA PLENA (CBS 8,8% / IBS 17,7%, carga cheia
da Reforma — consistente com uf_rates.py); isenção (CST 400) / imunidade (CST 410) → 0.
NÃO são as alíquotas reduzidas da fase de teste de 2026 (CBS 0,9% / IBS 0,1% — ver #315).

Revision ID: 2026_06_23_0020
Revises: 2026_05_31_0019
"""

from __future__ import annotations

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "2026_06_23_0020"
down_revision = "2026_05_31_0019"
branch_labels = None
depends_on = None

_CBS_PLENA = 8.8
_IBS_PLENA = 17.7
_ZERO_CSTS = {"400", "410"}  # isenção, imunidade/não incidência


def _regime(cst: str, red_cbs: float, red_ibs: float) -> str:
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


def upgrade() -> None:
    data_path = Path(__file__).resolve().parents[2] / "data" / "classtrib.json"
    by_code = json.loads(data_path.read_text(encoding="utf-8")).get("by_code", {})

    rows = []
    for code, it in by_code.items():
        cst = str(it.get("cst", ""))
        red_cbs = float(it.get("reduction_cbs_pct", 0) or 0)
        red_ibs = float(it.get("reduction_ibs_pct", 0) or 0)
        zero = cst in _ZERO_CSTS
        rows.append({
            "c": code,
            "d": (it.get("description") or "").strip() or code,
            "cbs": 0.0 if zero else round(_CBS_PLENA * (1 - red_cbs / 100), 4),
            "ibs": 0.0 if zero else round(_IBS_PLENA * (1 - red_ibs / 100), 4),
            "reg": _regime(cst, red_cbs, red_ibs),
            "vi": (it.get("vigencia_ini") or "2026-01-01") or "2026-01-01",
        })

    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM cclass_trib_items"))
    if rows:
        conn.execute(
            sa.text("""
                INSERT INTO cclass_trib_items
                    (codigo, descricao, p_cbs, p_ibs, regime_especial, vigencia_ini, is_active)
                VALUES (:c, :d, :cbs, :ibs, :reg, :vi, TRUE)
            """),
            rows,
        )


def downgrade() -> None:
    # Re-seed de dados — não reversível automaticamente (a migration 0018 repovoaria a
    # taxonomia de produto antiga). Mantido como no-op intencional.
    pass
