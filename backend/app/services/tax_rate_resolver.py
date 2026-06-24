"""
Tax Rate Resolver — resolves CBS/IBS rates and calculates tax amounts.

Hierarchy of rate resolution:
1. NCM-specific override (from ncm_rates.py — cesta básica, food, pharma, edu)
2. UF/Municipality default (from uf_rates.py — 27 states)
3. National reference fallback (CBS=8.8%, IBS≈17.7%)

The CST regime modifier is applied on top of the resolved rate.
For example, CST 001 (reduced) applies a 0.6 modifier → 60% of the rate.

All arithmetic uses Decimal for precision. Monetary values quantize to 0.01,
rates to 0.0001.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from pydantic import BaseModel

from app.data.uf_rates import (
    UF_RATES, CBS_NATIONAL_RATE, IBS_UF_DEFAULT, IBS_MUN_DEFAULT,
    CBS_TESTE_2026, IBS_2026_FACTOR,
)
from app.data.cst_regimes import get_rate_modifier, get_cst_regime, generates_tax
from app.data.ncm_rates import get_ncm_modifier

# Quantize helpers
_Q_RATE = Decimal("0.0001")
_Q_MONEY = Decimal("0.01")


class TaxRateResult(BaseModel):
    """Resolved tax rates for a given operation."""
    cbs_rate: Decimal
    ibs_uf_rate: Decimal
    ibs_mun_rate: Decimal
    ibs_total: Decimal
    rate_source: str          # "ncm" | "uf_default" | "national"
    cst_modifier: Decimal     # 1.0 normal, 0.6 reduced, 0.0 exempt
    ncm_modifier: Decimal     # 1.0 normal, 0.4 reduced, 0.0 zero-rated
    regime_desc: str


class CalculationResult(BaseModel):
    """Full tax calculation result with XML snippet."""
    vBC: Decimal              # Base de cálculo
    pCBS: Decimal             # Alíquota CBS efetiva
    vCBS: Decimal             # Valor CBS
    pIBSUF: Decimal           # Alíquota IBS UF efetiva
    vIBSUF: Decimal           # Valor IBS UF
    pIBSMun: Decimal          # Alíquota IBS Municipal efetiva
    vIBSMun: Decimal          # Valor IBS Municipal
    vIBS: Decimal             # Total IBS (UF + Mun)
    total_tributos: Decimal   # CBS + IBS
    aliquota_efetiva: Decimal # Total / vBC (percentage)
    rate_source: str
    cst: str
    cst_desc: str
    xml_snippet: str


def resolve_rates(
    ncm: str | None = None,
    uf: str | None = None,
    cst: str = "000",
    periodo: str = "regime_cheio",
) -> TaxRateResult:
    """Resolve CBS/IBS rates from the hierarchy: NCM → UF → National.

    Args:
        ncm: 8-digit NCM code (optional, for chapter-based overrides).
        uf: 2-letter UF code (optional, for state-specific rates).
        cst: 3-digit CST code (for regime modifier).

    Returns:
        TaxRateResult with resolved rates and modifiers.
    """
    # Step 1: Base rates from UF or national default
    rate_source = "national"
    cbs_rate = CBS_NATIONAL_RATE
    ibs_uf_rate = IBS_UF_DEFAULT
    ibs_mun_rate = IBS_MUN_DEFAULT

    if uf:
        uf_data = UF_RATES.get(uf.upper())
        if uf_data:
            cbs_rate = uf_data["cbs_rate"]
            ibs_uf_rate = uf_data["ibs_uf_rate"]
            ibs_mun_rate = uf_data["ibs_mun_rate"]
            rate_source = "uf_default"

    # Período de emissão: "teste_2026" (default) aplica as alíquotas reduzidas de 2026
    # (CBS 0,9% / IBS 0,1% total — o que vai na NF-e agora); "regime_cheio" mantém as
    # plenas resolvidas acima (projeção). O split IBS UF/Mun de 2026 escala o split plena.
    if periodo == "teste_2026":
        cbs_rate = CBS_TESTE_2026
        ibs_uf_rate = ibs_uf_rate * IBS_2026_FACTOR
        ibs_mun_rate = ibs_mun_rate * IBS_2026_FACTOR
        rate_source = f"{rate_source}_2026"

    # Step 2: NCM modifier (chapter-based overrides)
    ncm_mod = get_ncm_modifier(ncm or "")
    if ncm_mod != Decimal("1.0"):
        rate_source = "ncm"

    # Step 3: CST regime modifier
    cst_mod = get_rate_modifier(cst)
    regime = get_cst_regime(cst)
    regime_desc = regime["desc"] if regime else "Desconhecido"

    ibs_total = (ibs_uf_rate + ibs_mun_rate).quantize(_Q_RATE, ROUND_HALF_UP)

    return TaxRateResult(
        cbs_rate=cbs_rate,
        ibs_uf_rate=ibs_uf_rate,
        ibs_mun_rate=ibs_mun_rate,
        ibs_total=ibs_total,
        rate_source=rate_source,
        cst_modifier=cst_mod,
        ncm_modifier=ncm_mod,
        regime_desc=regime_desc,
    )


def calculate(
    vBC: Decimal,
    quantity: Decimal,
    rates: TaxRateResult,
) -> CalculationResult:
    """Calculate CBS/IBS amounts from base value and resolved rates.

    Args:
        vBC: Base de cálculo (valor da operação).
        quantity: Quantity (multiplied into base).
        rates: Resolved rates from resolve_rates().

    Returns:
        CalculationResult with all calculated values and XML snippet.
    """
    base = (vBC * quantity).quantize(_Q_MONEY, ROUND_HALF_UP)

    # Combined modifier: CST × NCM
    combined_mod = (rates.cst_modifier * rates.ncm_modifier).quantize(
        _Q_RATE, ROUND_HALF_UP
    )

    # Effective rates
    pCBS = (rates.cbs_rate * combined_mod).quantize(_Q_RATE, ROUND_HALF_UP)
    pIBSUF = (rates.ibs_uf_rate * combined_mod).quantize(_Q_RATE, ROUND_HALF_UP)
    pIBSMun = (rates.ibs_mun_rate * combined_mod).quantize(_Q_RATE, ROUND_HALF_UP)

    # Tax amounts
    vCBS = (base * pCBS).quantize(_Q_MONEY, ROUND_HALF_UP)
    vIBSUF = (base * pIBSUF).quantize(_Q_MONEY, ROUND_HALF_UP)
    vIBSMun = (base * pIBSMun).quantize(_Q_MONEY, ROUND_HALF_UP)
    vIBS = (vIBSUF + vIBSMun).quantize(_Q_MONEY, ROUND_HALF_UP)
    total = (vCBS + vIBS).quantize(_Q_MONEY, ROUND_HALF_UP)

    # Effective total rate
    aliquota_efetiva = Decimal("0.0000")
    if base > 0:
        aliquota_efetiva = (total / base).quantize(_Q_RATE, ROUND_HALF_UP)

    cst_regime = get_cst_regime(rates.regime_desc) if False else None  # noqa
    cst_desc = rates.regime_desc

    xml_snippet = generate_xml_snippet(
        cst="000",  # placeholder, overridden below
        vBC=base, pCBS=pCBS, vCBS=vCBS,
        pIBSUF=pIBSUF, vIBSUF=vIBSUF,
        pIBSMun=pIBSMun, vIBSMun=vIBSMun,
        vIBS=vIBS,
    )

    return CalculationResult(
        vBC=base,
        pCBS=pCBS, vCBS=vCBS,
        pIBSUF=pIBSUF, vIBSUF=vIBSUF,
        pIBSMun=pIBSMun, vIBSMun=vIBSMun,
        vIBS=vIBS,
        total_tributos=total,
        aliquota_efetiva=aliquota_efetiva,
        rate_source=rates.rate_source,
        cst="000",  # placeholder
        cst_desc=cst_desc,
        xml_snippet=xml_snippet,
    )


def calculate_full(
    vBC: Decimal,
    quantity: Decimal = Decimal("1"),
    ncm: str | None = None,
    uf: str | None = None,
    cst: str = "000",
    periodo: str = "regime_cheio",
) -> CalculationResult:
    """Convenience: resolve rates + calculate in one call.

    Args:
        vBC: Base de cálculo.
        quantity: Quantity (default 1).
        ncm: 8-digit NCM code (optional).
        uf: 2-letter UF code (optional).
        cst: 3-digit CST code (default "000").

    Returns:
        Full CalculationResult.
    """
    rates = resolve_rates(ncm=ncm, uf=uf, cst=cst, periodo=periodo)
    result = calculate(vBC, quantity, rates)

    # Override CST in the result
    regime = get_cst_regime(cst)
    cst_desc = regime["desc"] if regime else "Desconhecido"

    xml_snippet = generate_xml_snippet(
        cst=cst,
        vBC=result.vBC, pCBS=result.pCBS, vCBS=result.vCBS,
        pIBSUF=result.pIBSUF, vIBSUF=result.vIBSUF,
        pIBSMun=result.pIBSMun, vIBSMun=result.vIBSMun,
        vIBS=result.vIBS,
    )

    return CalculationResult(
        vBC=result.vBC,
        pCBS=result.pCBS, vCBS=result.vCBS,
        pIBSUF=result.pIBSUF, vIBSUF=result.vIBSUF,
        pIBSMun=result.pIBSMun, vIBSMun=result.vIBSMun,
        vIBS=result.vIBS,
        total_tributos=result.total_tributos,
        aliquota_efetiva=result.aliquota_efetiva,
        rate_source=result.rate_source,
        cst=cst,
        cst_desc=cst_desc,
        xml_snippet=xml_snippet,
    )


def generate_xml_snippet(
    cst: str,
    vBC: Decimal,
    pCBS: Decimal, vCBS: Decimal,
    pIBSUF: Decimal, vIBSUF: Decimal,
    pIBSMun: Decimal, vIBSMun: Decimal,
    vIBS: Decimal,
) -> str:
    """Generate an <IBSCBS> XML fragment for NF-e insertion.

    Returns well-formed XML ready to be pasted into <imposto> section.
    """
    if not generates_tax(cst):
        return (
            f"<IBSCBS>\n"
            f"  <CST>{cst}</CST>\n"
            f"</IBSCBS>"
        )

    return (
        f"<IBSCBS>\n"
        f"  <CST>{cst}</CST>\n"
        f"  <gIBSCBS>\n"
        f"    <vBC>{vBC}</vBC>\n"
        f"    <pCBS>{pCBS}</pCBS>\n"
        f"    <vCBS>{vCBS}</vCBS>\n"
        f"    <pIBSUF>{pIBSUF}</pIBSUF>\n"
        f"    <vIBSUF>{vIBSUF}</vIBSUF>\n"
        f"    <pIBSMun>{pIBSMun}</pIBSMun>\n"
        f"    <vIBSMun>{vIBSMun}</vIBSMun>\n"
        f"    <vIBS>{vIBS}</vIBS>\n"
        f"  </gIBSCBS>\n"
        f"</IBSCBS>"
    )
