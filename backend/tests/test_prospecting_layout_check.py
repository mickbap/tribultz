"""Validação de layout dos arquivos da RF (Ordem Complementar, item 2) — puro, sem DB."""

from pathlib import Path

import pytest

from app.services.prospecting.layout_check import (
    LayoutMismatchError,
    MalformedRowRatioError,
    check_malformed_ratio,
    compute_file_hashes,
    detect_layout_signature,
    sha256_file,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prospecting"


class TestDetectLayoutSignature:
    def test_real_fixtures_match_expected_layout(self):
        signature = detect_layout_signature(FIXTURE_DIR)
        assert "estabelecimentos:30campos" in signature
        assert "empresas:7campos" in signature
        assert "simples:7campos" in signature
        assert "socios:11campos" in signature

    def test_raises_when_field_count_mismatches(self, tmp_path):
        (tmp_path / "Empresas0.csv").write_text("10000000;RAZAO;2062;49;100000,00;5\n")  # 6 campos, faltou 1
        (tmp_path / "Estabelecimentos0.csv").write_text(
            ";".join(["x"] * 30) + "\n"
        )
        (tmp_path / "Simples0.csv").write_text(";".join(["x"] * 7) + "\n")
        (tmp_path / "Socios0.csv").write_text(";".join(["x"] * 11) + "\n")

        with pytest.raises(LayoutMismatchError, match="Empresas"):
            detect_layout_signature(tmp_path)

    def test_raises_when_table_file_missing(self, tmp_path):
        with pytest.raises(LayoutMismatchError):
            detect_layout_signature(tmp_path)


class TestFileHashing:
    def test_sha256_file_is_deterministic(self):
        path = FIXTURE_DIR / "Municipios0.csv"
        assert sha256_file(path) == sha256_file(path)

    def test_compute_file_hashes_covers_all_tables(self):
        hashes = compute_file_hashes(FIXTURE_DIR)
        assert any(name.startswith("Empresas") for name in hashes)
        assert any(name.startswith("Estabelecimentos") for name in hashes)
        assert any(name.startswith("Simples") for name in hashes)
        assert any(name.startswith("Socios") for name in hashes)
        assert any(name.startswith("Municipios") for name in hashes)
        assert all(len(h) == 64 for h in hashes.values())


class TestMalformedRowRatio:
    def test_within_tolerance_does_not_raise(self):
        check_malformed_ratio("Estabelecimentos0.csv", malformed=1, total=1000, max_ratio=0.01)

    def test_above_tolerance_raises(self):
        with pytest.raises(MalformedRowRatioError, match="Estabelecimentos0.csv"):
            check_malformed_ratio("Estabelecimentos0.csv", malformed=50, total=1000, max_ratio=0.01)

    def test_zero_total_does_not_raise(self):
        check_malformed_ratio("vazio.csv", malformed=0, total=0, max_ratio=0.01)
