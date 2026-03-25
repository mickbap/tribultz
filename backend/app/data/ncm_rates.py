"""
NCM-based rate overrides for CBS/IBS.

Certain product categories have reduced or zero rates under LC 214/2025.
This module maps NCM 2-digit chapter prefixes to rate modifiers.

Categories with special treatment (LC 214 Anexos):
- Food staples (Cesta Básica Nacional): 100% reduced (zero rate)
- Food general: 60% reduction
- Health/pharma: 60% reduction
- Education: 60% reduction
- Agriculture inputs: 60% reduction
- Personal hygiene: 60% reduction

The modifier is applied AFTER the CST regime modifier. For CST 000 (normal)
with a food NCM, the effective modifier = 1.0 × 0.4 = 0.4 (60% reduction).
"""

from decimal import Decimal


# NCM chapter (2-digit prefix) → rate modifier and description
# modifier < 1.0 means reduced rate; 0.0 means zero-rated
NCM_CHAPTER_OVERRIDES: dict[str, dict] = {
    # ── Cesta Básica Nacional (LC 214 Anexo I) — zero rate ──
    "02": {"modifier": Decimal("0.0"), "desc": "Carnes — Cesta Básica Nacional", "category": "cesta_basica"},
    "04": {"modifier": Decimal("0.0"), "desc": "Leite e ovos — Cesta Básica Nacional", "category": "cesta_basica"},
    "10": {"modifier": Decimal("0.0"), "desc": "Cereais — Cesta Básica Nacional", "category": "cesta_basica"},

    # ── Alimentos com redução de 60% (LC 214 Anexo II) ──
    "01": {"modifier": Decimal("0.4"), "desc": "Animais vivos — alíquota reduzida 60%", "category": "alimentos"},
    "03": {"modifier": Decimal("0.4"), "desc": "Peixes e crustáceos — alíquota reduzida 60%", "category": "alimentos"},
    "05": {"modifier": Decimal("0.4"), "desc": "Outros produtos de origem animal — redução 60%", "category": "alimentos"},
    "07": {"modifier": Decimal("0.4"), "desc": "Hortícolas — alíquota reduzida 60%", "category": "alimentos"},
    "08": {"modifier": Decimal("0.4"), "desc": "Frutas — alíquota reduzida 60%", "category": "alimentos"},
    "09": {"modifier": Decimal("0.4"), "desc": "Café, chá, mate — alíquota reduzida 60%", "category": "alimentos"},
    "11": {"modifier": Decimal("0.4"), "desc": "Produtos da indústria de moagem — redução 60%", "category": "alimentos"},
    "12": {"modifier": Decimal("0.4"), "desc": "Sementes e frutos oleaginosos — redução 60%", "category": "alimentos"},
    "15": {"modifier": Decimal("0.4"), "desc": "Gorduras e óleos — alíquota reduzida 60%", "category": "alimentos"},
    "16": {"modifier": Decimal("0.4"), "desc": "Preparações de carne/peixe — redução 60%", "category": "alimentos"},
    "17": {"modifier": Decimal("0.4"), "desc": "Açúcares — alíquota reduzida 60%", "category": "alimentos"},
    "19": {"modifier": Decimal("0.4"), "desc": "Preparações de cereais — redução 60%", "category": "alimentos"},
    "20": {"modifier": Decimal("0.4"), "desc": "Preparações de hortícolas/frutas — redução 60%", "category": "alimentos"},
    "21": {"modifier": Decimal("0.4"), "desc": "Preparações alimentícias diversas — redução 60%", "category": "alimentos"},
    "22": {"modifier": Decimal("0.4"), "desc": "Bebidas (não alcoólicas) — redução 60%", "category": "alimentos"},

    # ── Saúde e farmacêutico (LC 214 Anexo III) — redução 60% ──
    "30": {"modifier": Decimal("0.4"), "desc": "Produtos farmacêuticos — redução 60%", "category": "saude"},
    "33": {"modifier": Decimal("0.4"), "desc": "Higiene pessoal — redução 60%", "category": "saude"},
    "90": {"modifier": Decimal("0.4"), "desc": "Instrumentos médicos/cirúrgicos — redução 60%", "category": "saude"},

    # ── Educação (LC 214 Anexo IV) — redução 60% ──
    "49": {"modifier": Decimal("0.4"), "desc": "Livros, jornais, publicações — redução 60%", "category": "educacao"},

    # ── Insumos agropecuários (LC 214 Anexo V) — redução 60% ──
    "31": {"modifier": Decimal("0.4"), "desc": "Fertilizantes — redução 60%", "category": "agro"},
    "38": {"modifier": Decimal("0.4"), "desc": "Produtos químicos agrícolas — redução 60%", "category": "agro"},
}


def get_ncm_rate_override(ncm: str) -> dict | None:
    """Look up rate override by NCM chapter (first 2 digits).

    Returns dict with 'modifier', 'desc', 'category' or None if no override.
    """
    if not ncm or len(ncm) < 2:
        return None
    chapter = ncm[:2]
    return NCM_CHAPTER_OVERRIDES.get(chapter)


def get_ncm_modifier(ncm: str) -> Decimal:
    """Return the rate modifier for an NCM code. Defaults to 1.0 (full rate)."""
    override = get_ncm_rate_override(ncm)
    if override is None:
        return Decimal("1.0")
    return override["modifier"]
