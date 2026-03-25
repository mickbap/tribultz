"""Tests for static data modules used by the calculadora CBS/IBS."""

from decimal import Decimal

from app.data.uf_rates import (
    UF_RATES, VALID_UF_CODES, CBS_NATIONAL_RATE,
    get_uf_rates, is_valid_uf,
)
from app.data.cst_regimes import (
    CST_REGIMES, get_cst_regime, get_rate_modifier, generates_tax,
)
from app.data.ncm_rates import (
    NCM_CHAPTER_OVERRIDES, get_ncm_rate_override, get_ncm_modifier,
)
from app.data.ncm_codes import VALID_NCM_CODES, NCM_DESCRIPTIONS


# ── UF Rates ─────────────────────────────────────────────────────────────────

class TestUfRates:
    def test_all_27_states_present(self):
        assert len(UF_RATES) == 27

    def test_valid_uf_codes_match(self):
        assert len(VALID_UF_CODES) == 27
        assert VALID_UF_CODES == frozenset(UF_RATES.keys())

    def test_each_uf_has_required_fields(self):
        for uf, data in UF_RATES.items():
            assert "uf_name" in data, f"{uf} missing uf_name"
            assert "cbs_rate" in data, f"{uf} missing cbs_rate"
            assert "ibs_uf_rate" in data, f"{uf} missing ibs_uf_rate"
            assert "ibs_mun_rate" in data, f"{uf} missing ibs_mun_rate"

    def test_cbs_rate_is_uniform(self):
        for uf, data in UF_RATES.items():
            assert data["cbs_rate"] == CBS_NATIONAL_RATE, f"{uf} CBS rate mismatch"

    def test_rates_are_positive_decimals(self):
        for uf, data in UF_RATES.items():
            assert isinstance(data["cbs_rate"], Decimal)
            assert data["cbs_rate"] > 0
            assert data["ibs_uf_rate"] > 0
            assert data["ibs_mun_rate"] > 0

    def test_ibs_total_reasonable(self):
        """IBS UF + Mun should be roughly 17-18% for all states."""
        for uf, data in UF_RATES.items():
            total = data["ibs_uf_rate"] + data["ibs_mun_rate"]
            assert Decimal("0.15") < total < Decimal("0.20"), f"{uf} IBS total {total} out of range"

    def test_get_uf_rates_valid(self):
        rates = get_uf_rates("SP")
        assert rates is not None
        assert rates["uf_name"] == "São Paulo"

    def test_get_uf_rates_case_insensitive(self):
        assert get_uf_rates("sp") is not None

    def test_get_uf_rates_invalid(self):
        assert get_uf_rates("XX") is None

    def test_is_valid_uf(self):
        assert is_valid_uf("SP")
        assert is_valid_uf("rj")
        assert not is_valid_uf("XX")

    def test_known_states(self):
        expected = {"AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
                    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
                    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"}
        assert VALID_UF_CODES == expected


# ── CST Regimes ──────────────────────────────────────────────────────────────

class TestCstRegimes:
    def test_14_cst_codes(self):
        assert len(CST_REGIMES) == 14

    def test_each_cst_has_required_fields(self):
        for cst, data in CST_REGIMES.items():
            assert "desc" in data, f"{cst} missing desc"
            assert "rate_modifier" in data, f"{cst} missing rate_modifier"
            assert "generates_tax" in data, f"{cst} missing generates_tax"
            assert "xml_group" in data, f"{cst} missing xml_group"
            assert "regime" in data, f"{cst} missing regime"

    def test_normal_cst_000(self):
        regime = get_cst_regime("000")
        assert regime["rate_modifier"] == Decimal("1.0")
        assert regime["generates_tax"] is True
        assert regime["regime"] == "normal"

    def test_reduced_cst_001(self):
        regime = get_cst_regime("001")
        assert regime["rate_modifier"] == Decimal("0.6")
        assert regime["generates_tax"] is True
        assert regime["regime"] == "reduzido"

    def test_exempt_cst_070(self):
        regime = get_cst_regime("070")
        assert regime["rate_modifier"] == Decimal("0.0")
        assert regime["generates_tax"] is False
        assert regime["regime"] == "isento"

    def test_suspended_cst_410(self):
        regime = get_cst_regime("410")
        assert regime["rate_modifier"] == Decimal("0.0")
        assert regime["generates_tax"] is False

    def test_get_rate_modifier_normal(self):
        assert get_rate_modifier("000") == Decimal("1.0")

    def test_get_rate_modifier_unknown_defaults_to_1(self):
        assert get_rate_modifier("999") == Decimal("1.0")

    def test_generates_tax_for_normal(self):
        assert generates_tax("000") is True

    def test_generates_tax_for_exempt(self):
        assert generates_tax("070") is False

    def test_modifiers_in_valid_range(self):
        for cst, data in CST_REGIMES.items():
            mod = data["rate_modifier"]
            assert Decimal("0") <= mod <= Decimal("1"), f"{cst} modifier {mod} out of range"


# ── NCM Rate Overrides ───────────────────────────────────────────────────────

class TestNcmRates:
    def test_has_overrides(self):
        assert len(NCM_CHAPTER_OVERRIDES) >= 20

    def test_cesta_basica_zero_rate(self):
        meat = get_ncm_rate_override("02011000")
        assert meat is not None
        assert meat["modifier"] == Decimal("0.0")
        assert meat["category"] == "cesta_basica"

    def test_food_reduced_rate(self):
        fish = get_ncm_rate_override("03034100")
        assert fish is not None
        assert fish["modifier"] == Decimal("0.4")
        assert fish["category"] == "alimentos"

    def test_pharma_reduced_rate(self):
        pharma = get_ncm_rate_override("30049099")
        assert pharma is not None
        assert pharma["modifier"] == Decimal("0.4")
        assert pharma["category"] == "saude"

    def test_education_reduced_rate(self):
        books = get_ncm_rate_override("49019900")
        assert books is not None
        assert books["modifier"] == Decimal("0.4")
        assert books["category"] == "educacao"

    def test_industrial_no_override(self):
        """Chapter 84 (machinery) has no special rate."""
        result = get_ncm_rate_override("84713012")
        assert result is None

    def test_get_ncm_modifier_with_override(self):
        assert get_ncm_modifier("02011000") == Decimal("0.0")

    def test_get_ncm_modifier_without_override(self):
        assert get_ncm_modifier("84713012") == Decimal("1.0")

    def test_get_ncm_modifier_empty(self):
        assert get_ncm_modifier("") == Decimal("1.0")

    def test_each_override_has_required_fields(self):
        for ch, data in NCM_CHAPTER_OVERRIDES.items():
            assert "modifier" in data, f"Chapter {ch} missing modifier"
            assert "desc" in data, f"Chapter {ch} missing desc"
            assert "category" in data, f"Chapter {ch} missing category"


# ── NCM Descriptions ─────────────────────────────────────────────────────────

class TestNcmDescriptions:
    def test_descriptions_match_codes(self):
        """Every NCM code should have a description."""
        for code in VALID_NCM_CODES:
            assert code in NCM_DESCRIPTIONS, f"NCM {code} missing description"

    def test_descriptions_count(self):
        assert len(NCM_DESCRIPTIONS) == len(VALID_NCM_CODES)

    def test_descriptions_are_nonempty(self):
        for code, desc in NCM_DESCRIPTIONS.items():
            assert desc.strip(), f"NCM {code} has empty description"

    def test_known_ncm_description(self):
        assert "84713012" in NCM_DESCRIPTIONS
        desc = NCM_DESCRIPTIONS["84713012"]
        assert len(desc) > 5
