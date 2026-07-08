"""Partner Code — regras de formato (RFC-0025). Sem DB.

Único · uppercase · sem acento/espaço · [A-Z0-9_-] · 3–32 chars.
"""

import pytest

from app.models.partner import PARTNER_STATUSES, PARTNER_TYPES, normalize_partner_code


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("KATIA", "KATIA"),
        ("katia", "KATIA"),            # normaliza para uppercase
        ("  duquesa  ", "DUQUESA"),    # trim
        ("ACIJOINVILLE", "ACIJOINVILLE"),
        ("INSI", "INSI"),
        ("A-B_C0", "A-B_C0"),          # hífen, underscore e dígito são válidos
        ("ABC", "ABC"),                # mínimo 3
        ("A" * 32, "A" * 32),          # máximo 32
    ],
)
def test_codigos_validos_normalizam(raw, expected):
    assert normalize_partner_code(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",              # vazio
        None,            # ausente
        "ab",            # curto demais (2)
        "A" * 33,        # longo demais (33)
        "com espaco",    # espaço no meio
        "acentuação",    # acento
        "KA!TIA",        # símbolo fora do conjunto
        "kátia",         # acento minúsculo
        "a.b",           # ponto não permitido
    ],
)
def test_codigos_invalidos_viram_none(raw):
    assert normalize_partner_code(raw) is None


def test_catalogo_de_tipos_rfc_0025():
    assert PARTNER_TYPES == (
        "lawyer",
        "accountant",
        "consultancy",
        "erp",
        "association",
        "influencer",
        "other",
    )


def test_status_possiveis():
    assert PARTNER_STATUSES == ("active", "inactive")
