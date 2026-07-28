"""Parser em streaming dos arquivos da RF (PO-2026-07-SALES-001, Fase 1) — puro, sem DB.

Fixtures sintéticas em tests/fixtures/prospecting/ (mesmo formato ;-separado, sem
cabeçalho, dos arquivos reais — geradas a partir das próprias tuplas de campo de
rf_parser.py, então qualquer mudança na ordem dos campos quebra os dois lados
juntos, não silenciosamente).
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

from app.services.prospecting.rf_parser import (
    iter_empresas,
    iter_estabelecimentos,
    iter_simples,
    iter_socios,
    load_municipios,
    parse_bool_sn,
    parse_cnaes_secundarios,
    parse_date_yyyymmdd,
    parse_decimal_br,
    parse_porte,
    parse_situacao_cadastral,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prospecting"


class TestStreamingReaders:
    def test_iter_estabelecimentos_reads_all_rows(self):
        rows = list(iter_estabelecimentos(FIXTURE_DIR))
        assert len(rows) == 7  # 3 (ALPHA) + 1 (BETA) + 1 (GAMA) + 1 (DELTA) + 1 (LOJA)

    def test_iter_empresas_reads_all_rows(self):
        assert len(list(iter_empresas(FIXTURE_DIR))) == 5

    def test_iter_simples_reads_all_rows(self):
        assert len(list(iter_simples(FIXTURE_DIR))) == 5

    def test_iter_socios_reads_all_rows(self):
        assert len(list(iter_socios(FIXTURE_DIR))) == 7

    def test_load_municipios_builds_code_to_name_dict(self):
        municipios = load_municipios(FIXTURE_DIR)
        assert municipios["4314902"] == "PORTO ALEGRE"
        assert len(municipios) == 5


class TestNormalizationHelpers:
    def test_parse_situacao_cadastral_normalizes_via_int(self):
        # Ambiguidade de zero à esquerda no PDF (01/2/3/4/08) -> normalizado via
        # int(), nunca comparado como string bruta.
        assert parse_situacao_cadastral("2") == 2
        assert parse_situacao_cadastral("02") == 2
        assert parse_situacao_cadastral("") is None

    def test_parse_porte_normalizes_to_two_digit_string(self):
        assert parse_porte("5") == "05"
        assert parse_porte("05") == "05"
        assert parse_porte("0") == "00"
        assert parse_porte("") == "00"

    def test_parse_bool_sn(self):
        assert parse_bool_sn("S") is True
        assert parse_bool_sn("s") is True
        assert parse_bool_sn("N") is False
        assert parse_bool_sn("") is False

    def test_parse_decimal_br_handles_comma_separator(self):
        assert parse_decimal_br("150000,00") == Decimal("150000.00")
        assert parse_decimal_br("") == Decimal("0")
        assert parse_decimal_br("1.500.000,50") == Decimal("1500000.50")

    def test_parse_date_yyyymmdd(self):
        assert parse_date_yyyymmdd("20100115") == date(2010, 1, 15)
        assert parse_date_yyyymmdd("") is None
        assert parse_date_yyyymmdd("00000000") is None

    def test_parse_cnaes_secundarios_splits_on_comma(self):
        assert parse_cnaes_secundarios("6920601,4713002") == ["6920601", "4713002"]
        assert parse_cnaes_secundarios("") == []
