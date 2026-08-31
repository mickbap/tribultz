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
    resolve_ncm_modifier,
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
        assert regime is not None
        assert regime["rate_modifier"] == Decimal("1.0")
        assert regime["generates_tax"] is True
        assert regime["regime"] == "normal"

    def test_reduced_cst_001(self):
        regime = get_cst_regime("001")
        assert regime is not None
        assert regime["rate_modifier"] == Decimal("0.6")
        assert regime["generates_tax"] is True
        assert regime["regime"] == "reduzido"

    def test_exempt_cst_070(self):
        regime = get_cst_regime("070")
        assert regime is not None
        assert regime["rate_modifier"] == Decimal("0.0")
        assert regime["generates_tax"] is False
        assert regime["regime"] == "isento"

    def test_suspended_cst_410(self):
        regime = get_cst_regime("410")
        assert regime is not None
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


# ── NCM: modificador com lastro na fonte (#685, decisão C) ───────────────────

class TestNcmModifierLastro:
    """A derivação por capítulo NCM foi removida: 19 dos 24 capítulos divergiam
    da fonte e seis NCMs recebiam imposto zerado onde a fonte só sustenta 60%.
    """

    def test_a_trigo_lastro_unanime_60(self):
        """A) NCM 10019900 — três cClassTrib, todos com redução de 60%."""
        r = resolve_ncm_modifier("10019900")
        assert r.modifier == Decimal("0.4"), "60% de redução → modificador 0.4"
        assert r.unanime is True
        assert r.nao_determinavel is False
        assert set(r.fontes) == {"200034", "200038", "515001"}

    def test_b_ncm_ambigua_nao_determinavel(self):
        """B) tratamentos divergentes na mesma NCM → nao_determinavel."""
        r = resolve_ncm_modifier("06024000")   # tratamentos divergentes na fonte
        assert r.nao_determinavel is True
        assert r.unanime is False
        assert r.modifier is None, "nenhum modificador inventado"
        assert r.fontes, "as fontes consultadas continuam visíveis"

    def test_c_ncm_sem_lastro_nao_determinavel(self):
        """C) sem cClassTrib de lastro → nao_determinavel, não 1.0."""
        r = resolve_ncm_modifier("84713012")
        assert r.nao_determinavel is True
        assert r.modifier is None
        assert r.fontes == ()

    def test_d_outro_lastro_unanime(self):
        """D) NCM unânime diferente do trigo devolve o valor da fonte."""
        r = resolve_ncm_modifier("04090000")
        assert r.modifier == Decimal("0.4")
        assert r.unanime is True

    def test_e_regressao_os_seis_ncms_zerados(self):
        """E) nenhum dos seis pode voltar a receber imposto zerado.

        Eram o caso mais grave: a tabela por capítulo zerava o imposto onde a
        fonte, unânime, sustenta apenas 60%.
        """
        for ncm in ("04090000", "10011100", "10019900", "10051000", "10059010", "10059090"):
            r = resolve_ncm_modifier(ncm)
            assert r.unanime is True, ncm
            assert r.modifier == Decimal("0.4"), f"{ncm} voltou a divergir da fonte"
            assert r.modifier != Decimal("0.0"), f"{ncm} zerado contra a fonte"

    def test_ncm_vazio_nao_determinavel(self):
        assert resolve_ncm_modifier("").nao_determinavel is True
        assert resolve_ncm_modifier(None).nao_determinavel is True

    def test_derivacao_por_capitulo_nao_existe_mais(self):
        """A heurística não pode voltar por outra porta."""
        import app.data.ncm_rates as mod

        assert not hasattr(mod, "NCM_CHAPTER_OVERRIDES"), "tabela manual por capítulo reintroduzida"
        assert not hasattr(mod, "get_ncm_rate_override"), "lookup por capítulo reintroduzido"
        # Duas NCMs do MESMO capítulo com lastros diferentes não podem colapsar.
        assert resolve_ncm_modifier("10019900").modifier == Decimal("0.4")
        assert resolve_ncm_modifier("10011100").modifier == Decimal("0.4")



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
