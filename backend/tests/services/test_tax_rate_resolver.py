"""Tests for the Tax Rate Resolver service."""

from decimal import Decimal

from app.services.tax_rate_resolver import (
    resolve_rates, calculate, calculate_full, generate_xml_snippet,
)
from app.data.uf_rates import CBS_NATIONAL_RATE


class TestResolveRates:
    def test_national_fallback_no_uf(self):
        rates = resolve_rates()
        assert rates.rate_source == "national"
        assert rates.cbs_rate == CBS_NATIONAL_RATE

    def test_uf_rate_override(self):
        rates = resolve_rates(uf="SP")
        assert rates.rate_source == "uf_default"
        assert rates.cbs_rate == Decimal("0.0880")
        assert rates.ibs_uf_rate == Decimal("0.1130")

    def test_uf_case_insensitive(self):
        rates = resolve_rates(uf="sp")
        assert rates.rate_source == "uf_default"

    def test_invalid_uf_falls_back_to_national(self):
        rates = resolve_rates(uf="XX")
        assert rates.rate_source == "national"

    def test_ncm_override_cesta_basica(self):
        rates = resolve_rates(ncm="02011000", uf="SP")
        assert rates.rate_source == "ncm"
        assert rates.ncm_modifier == Decimal("0.0")

    def test_ncm_override_food_reduced(self):
        rates = resolve_rates(ncm="03034100", uf="SP")
        assert rates.rate_source == "ncm"
        assert rates.ncm_modifier == Decimal("0.4")

    def test_ncm_no_override(self):
        rates = resolve_rates(ncm="84713012", uf="SP")
        assert rates.rate_source == "uf_default"
        assert rates.ncm_modifier == Decimal("1.0")

    def test_cst_exempt_070(self):
        rates = resolve_rates(uf="SP", cst="070")
        assert rates.cst_modifier == Decimal("0.0")
        assert "Imunidade" in rates.regime_desc or "Isen" in rates.regime_desc

    def test_cst_reduced_001(self):
        rates = resolve_rates(uf="SP", cst="001")
        assert rates.cst_modifier == Decimal("0.6")

    def test_cst_suspended_410(self):
        rates = resolve_rates(uf="SP", cst="410")
        assert rates.cst_modifier == Decimal("0.0")

    def test_ibs_total_is_sum(self):
        rates = resolve_rates(uf="RJ")
        expected = rates.ibs_uf_rate + rates.ibs_mun_rate
        assert rates.ibs_total == expected.quantize(Decimal("0.0001"))


class TestCalculate:
    def test_normal_calculation_sp(self):
        rates = resolve_rates(uf="SP", cst="000")
        result = calculate(Decimal("1000.00"), Decimal("1"), rates)
        assert result.vBC == Decimal("1000.00")
        assert result.vCBS == Decimal("88.00")  # 1000 × 0.0880
        assert result.vIBS == result.vIBSUF + result.vIBSMun
        assert result.total_tributos == result.vCBS + result.vIBS
        assert result.total_tributos > 0

    def test_exempt_cst_zero_tax(self):
        rates = resolve_rates(uf="SP", cst="070")
        result = calculate(Decimal("1000.00"), Decimal("1"), rates)
        assert result.vCBS == Decimal("0.00")
        assert result.vIBS == Decimal("0.00")
        assert result.total_tributos == Decimal("0.00")
        assert result.aliquota_efetiva == Decimal("0.0000")

    def test_reduced_cst_001(self):
        rates = resolve_rates(uf="SP", cst="001")
        result = calculate(Decimal("1000.00"), Decimal("1"), rates)
        # 60% of normal rate
        normal_rates = resolve_rates(uf="SP", cst="000")
        normal_result = calculate(Decimal("1000.00"), Decimal("1"), normal_rates)
        assert result.vCBS < normal_result.vCBS
        assert result.total_tributos < normal_result.total_tributos

    def test_quantity_multiplier(self):
        rates = resolve_rates(uf="SP", cst="000")
        result_1 = calculate(Decimal("100.00"), Decimal("1"), rates)
        result_5 = calculate(Decimal("100.00"), Decimal("5"), rates)
        assert result_5.vBC == Decimal("500.00")
        assert result_5.total_tributos == result_1.total_tributos * 5

    def test_cesta_basica_zero_rate(self):
        rates = resolve_rates(ncm="02011000", uf="SP", cst="000")
        result = calculate(Decimal("1000.00"), Decimal("1"), rates)
        assert result.vCBS == Decimal("0.00")
        assert result.vIBS == Decimal("0.00")

    def test_effective_rate(self):
        rates = resolve_rates(uf="SP", cst="000")
        result = calculate(Decimal("1000.00"), Decimal("1"), rates)
        expected = result.total_tributos / result.vBC
        assert result.aliquota_efetiva == expected.quantize(Decimal("0.0001"))

    def test_zero_base_no_crash(self):
        rates = resolve_rates(uf="SP")
        result = calculate(Decimal("0.00"), Decimal("1"), rates)
        assert result.total_tributos == Decimal("0.00")
        assert result.aliquota_efetiva == Decimal("0.0000")


class TestCalculateFull:
    def test_convenience_method(self):
        result = calculate_full(
            vBC=Decimal("1000.00"), ncm="84713012", uf="SP", cst="000",
        )
        assert result.cst == "000"
        assert result.vBC == Decimal("1000.00")
        assert result.total_tributos > 0
        assert "<IBSCBS>" in result.xml_snippet
        assert "<CST>000</CST>" in result.xml_snippet

    def test_exempt_cst_xml(self):
        result = calculate_full(
            vBC=Decimal("1000.00"), uf="SP", cst="070",
        )
        assert result.cst == "070"
        assert result.total_tributos == Decimal("0.00")
        assert "<CST>070</CST>" in result.xml_snippet
        assert "<gIBSCBS>" not in result.xml_snippet


class TestGenerateXmlSnippet:
    def test_normal_cst_has_group(self):
        xml = generate_xml_snippet(
            cst="000", vBC=Decimal("1000.00"),
            pCBS=Decimal("0.0880"), vCBS=Decimal("88.00"),
            pIBSUF=Decimal("0.1130"), vIBSUF=Decimal("113.00"),
            pIBSMun=Decimal("0.0640"), vIBSMun=Decimal("64.00"),
            vIBS=Decimal("177.00"),
        )
        assert "<IBSCBS>" in xml
        assert "<gIBSCBS>" in xml
        assert "<CST>000</CST>" in xml
        assert "<vBC>1000.00</vBC>" in xml
        assert "<vCBS>88.00</vCBS>" in xml

    def test_exempt_cst_no_group(self):
        xml = generate_xml_snippet(
            cst="070", vBC=Decimal("0"), pCBS=Decimal("0"),
            vCBS=Decimal("0"), pIBSUF=Decimal("0"), vIBSUF=Decimal("0"),
            pIBSMun=Decimal("0"), vIBSMun=Decimal("0"), vIBS=Decimal("0"),
        )
        assert "<CST>070</CST>" in xml
        assert "<gIBSCBS>" not in xml

    def test_suspended_cst_no_group(self):
        xml = generate_xml_snippet(
            cst="410", vBC=Decimal("0"), pCBS=Decimal("0"),
            vCBS=Decimal("0"), pIBSUF=Decimal("0"), vIBSUF=Decimal("0"),
            pIBSMun=Decimal("0"), vIBSMun=Decimal("0"), vIBS=Decimal("0"),
        )
        assert "<CST>410</CST>" in xml
        assert "<gIBSCBS>" not in xml
