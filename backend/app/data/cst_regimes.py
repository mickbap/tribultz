"""
CST (Código de Situação Tributária) regime mapping for IBS/CBS.

Maps each CST code to its tax treatment: rate modifier, whether it generates
tax values, and the expected XML group in the NF-e.

Aligned with CST_TABLE in validate_xml.py and NT 2025.002-RTC.
"""

from decimal import Decimal

CST_REGIMES: dict[str, dict] = {
    "000": {
        "desc": "Tributação normal (ad valorem)",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "normal",
    },
    "001": {
        "desc": "Tributação normal com redução",
        "rate_modifier": Decimal("0.6"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "reduzido",
    },
    "002": {
        "desc": "Tributação ad rem (monofásico por unidade)",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBSMono",
        "regime": "ad_rem",
    },
    "070": {
        "desc": "Imunidade / Isenção",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": None,
        "regime": "isento",
    },
    "200": {
        "desc": "Diferimento",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "diferimento",
    },
    "410": {
        "desc": "Suspensão",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": None,
        "regime": "suspenso",
    },
    "510": {
        "desc": "Crédito presumido",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "credito_presumido",
    },
    "515": {
        "desc": "Crédito presumido especial",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "credito_presumido_especial",
    },
    "550": {
        "desc": "Regime específico",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBS",
        "regime": "especifico",
    },
    "620": {
        "desc": "Monofásico",
        "rate_modifier": Decimal("1.0"),
        "generates_tax": True,
        "xml_group": "gIBSCBSMono",
        "regime": "monofasico",
    },
    "800": {
        "desc": "Transferência de crédito",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": "gTransfCred",
        "regime": "transferencia",
    },
    "810": {
        "desc": "Ressarcimento",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": None,
        "regime": "ressarcimento",
    },
    "811": {
        "desc": "Ajuste de competência",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": "gAjusteCompet",
        "regime": "ajuste",
    },
    "830": {
        "desc": "Estorno de crédito",
        "rate_modifier": Decimal("0.0"),
        "generates_tax": False,
        "xml_group": "gEstornoCred",
        "regime": "estorno",
    },
}


def get_cst_regime(cst: str) -> dict | None:
    """Return regime info for a CST code, or None if invalid."""
    return CST_REGIMES.get(cst)


def get_rate_modifier(cst: str) -> Decimal:
    """Return the rate modifier for a CST code. Defaults to 1.0 (full rate)."""
    regime = CST_REGIMES.get(cst)
    if regime is None:
        return Decimal("1.0")
    return regime["rate_modifier"]


def generates_tax(cst: str) -> bool:
    """Whether this CST generates CBS/IBS tax values."""
    regime = CST_REGIMES.get(cst)
    if regime is None:
        return True
    return regime["generates_tax"]
