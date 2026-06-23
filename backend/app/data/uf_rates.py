"""
Reference CBS/IBS tax rates by Brazilian state (UF).

Estes são os valores de REFERÊNCIA PLENA (carga cheia da Reforma, LC 214/2025),
usados para projeção/planejamento de longo prazo. NÃO são as alíquotas reduzidas
da fase de teste de 2026 (CBS 0,9% / IBS 0,1%): durante a transição 2026-2032 as
alíquotas efetivas de emissão são frações destas. Os valores abaixo NÃO devem ser
lidos como a alíquota vigente de emissão em 2026 (ver #315).

The IBS rate is split between state (UF) and municipality (Mun) components.
CBS (federal): uniform national rate.
IBS UF (state): varies by state — transition period 2026-2032.
IBS Mun (municipal): varies by municipality — uses state average as default.
"""

from decimal import Decimal

# National reference rates (LC 214 Art. 9)
CBS_NATIONAL_RATE = Decimal("0.0880")       # 8.80% CBS federal
IBS_NATIONAL_RATE = Decimal("0.1770")       # 17.70% IBS total (UF + Mun)
IBS_UF_DEFAULT = Decimal("0.1130")          # ~11.30% state share (avg)
IBS_MUN_DEFAULT = Decimal("0.0640")         # ~6.40% municipal share (avg)


UF_RATES: dict[str, dict] = {
    "AC": {"uf_name": "Acre", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1100"), "ibs_mun_rate": Decimal("0.0670")},
    "AL": {"uf_name": "Alagoas", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "AM": {"uf_name": "Amazonas", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1100"), "ibs_mun_rate": Decimal("0.0670")},
    "AP": {"uf_name": "Amapá", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1100"), "ibs_mun_rate": Decimal("0.0670")},
    "BA": {"uf_name": "Bahia", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1160"), "ibs_mun_rate": Decimal("0.0610")},
    "CE": {"uf_name": "Ceará", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1140"), "ibs_mun_rate": Decimal("0.0630")},
    "DF": {"uf_name": "Distrito Federal", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1130"), "ibs_mun_rate": Decimal("0.0640")},
    "ES": {"uf_name": "Espírito Santo", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1120"), "ibs_mun_rate": Decimal("0.0650")},
    "GO": {"uf_name": "Goiás", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1140"), "ibs_mun_rate": Decimal("0.0630")},
    "MA": {"uf_name": "Maranhão", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "MG": {"uf_name": "Minas Gerais", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1130"), "ibs_mun_rate": Decimal("0.0640")},
    "MS": {"uf_name": "Mato Grosso do Sul", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1140"), "ibs_mun_rate": Decimal("0.0630")},
    "MT": {"uf_name": "Mato Grosso", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1140"), "ibs_mun_rate": Decimal("0.0630")},
    "PA": {"uf_name": "Pará", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "PB": {"uf_name": "Paraíba", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "PE": {"uf_name": "Pernambuco", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "PI": {"uf_name": "Piauí", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "PR": {"uf_name": "Paraná", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1120"), "ibs_mun_rate": Decimal("0.0650")},
    "RJ": {"uf_name": "Rio de Janeiro", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1130"), "ibs_mun_rate": Decimal("0.0640")},
    "RN": {"uf_name": "Rio Grande do Norte", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "RO": {"uf_name": "Rondônia", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1110"), "ibs_mun_rate": Decimal("0.0660")},
    "RR": {"uf_name": "Roraima", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1100"), "ibs_mun_rate": Decimal("0.0670")},
    "RS": {"uf_name": "Rio Grande do Sul", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1120"), "ibs_mun_rate": Decimal("0.0650")},
    "SC": {"uf_name": "Santa Catarina", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1110"), "ibs_mun_rate": Decimal("0.0660")},
    "SE": {"uf_name": "Sergipe", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1150"), "ibs_mun_rate": Decimal("0.0620")},
    "SP": {"uf_name": "São Paulo", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1130"), "ibs_mun_rate": Decimal("0.0640")},
    "TO": {"uf_name": "Tocantins", "cbs_rate": Decimal("0.0880"), "ibs_uf_rate": Decimal("0.1140"), "ibs_mun_rate": Decimal("0.0630")},
}

VALID_UF_CODES: frozenset[str] = frozenset(UF_RATES.keys())


def get_uf_rates(uf: str) -> dict | None:
    """Return rates for a UF code, or None if invalid."""
    return UF_RATES.get(uf.upper())


def is_valid_uf(uf: str) -> bool:
    """Check if UF code is valid."""
    return uf.upper() in VALID_UF_CODES
