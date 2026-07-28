"""Guarda de sanidade de volume (Ordem Complementar, item 1) — puro, sem DB."""

import pytest
import yaml

from app.services.prospecting.sanity import (
    IngestionMetrics,
    SanityCheckError,
    load_thresholds,
    reduction_summary,
    thresholds_checksum,
    validate_metrics,
)


def _metrics(**overrides) -> IngestionMetrics:
    defaults = dict(
        total_estabelecimentos_scanned=1_000_000,
        total_target_cnae_found=80_000,
        total_ativas=70_000,
        total_consolidated=70_000,
    )
    defaults.update(overrides)
    return IngestionMetrics(**defaults)


class TestLoadThresholds:
    def test_loads_real_thresholds_file(self):
        thresholds = load_thresholds()
        assert thresholds["min_target_cnae_found"] > 0
        assert 0 < thresholds["min_ativas_ratio"] <= 1

    def test_checksum_is_stable(self):
        assert thresholds_checksum() == thresholds_checksum()

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SanityCheckError):
            load_thresholds(tmp_path / "nao_existe.yaml")

    def test_missing_key_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(yaml.safe_dump({"min_target_cnae_found": 1}))
        with pytest.raises(SanityCheckError, match="max_target_cnae_found"):
            load_thresholds(bad)


class TestValidateMetrics:
    def test_healthy_metrics_pass(self):
        thresholds = load_thresholds()
        validate_metrics(_metrics(), thresholds)  # não deve levantar

    def test_zero_eligible_raises(self):
        thresholds = load_thresholds()
        with pytest.raises(SanityCheckError, match="Zero empresas elegíveis"):
            validate_metrics(_metrics(total_target_cnae_found=0, total_ativas=0), thresholds)

    def test_below_min_target_raises(self):
        thresholds = load_thresholds()
        with pytest.raises(SanityCheckError, match="fora da"):
            validate_metrics(_metrics(total_target_cnae_found=10, total_ativas=8), thresholds)

    def test_above_max_target_raises(self):
        thresholds = load_thresholds()
        with pytest.raises(SanityCheckError, match="fora da"):
            validate_metrics(
                _metrics(total_target_cnae_found=10_000_000, total_ativas=9_000_000), thresholds
            )

    def test_low_ativas_ratio_raises(self):
        thresholds = load_thresholds()
        with pytest.raises(SanityCheckError, match="ativas"):
            validate_metrics(_metrics(total_target_cnae_found=80_000, total_ativas=1_000), thresholds)

    def test_first_run_without_baseline_does_not_check_relative_change(self):
        thresholds = load_thresholds()
        # Sem "previous" — mesmo uma métrica que seria uma variação absurda vs.
        # qualquer coisa não deve travar por falta de comparação.
        validate_metrics(_metrics(total_target_cnae_found=200_000, total_ativas=150_000), thresholds)

    def test_relative_change_within_tolerance_passes(self):
        thresholds = load_thresholds()
        previous = _metrics(total_target_cnae_found=80_000, total_ativas=70_000)
        current = _metrics(total_target_cnae_found=100_000, total_ativas=90_000)  # +25%
        validate_metrics(current, thresholds, previous=previous)

    def test_relative_change_above_tolerance_raises(self):
        thresholds = load_thresholds()
        previous = _metrics(total_target_cnae_found=80_000, total_ativas=70_000)
        current = _metrics(total_target_cnae_found=200_000, total_ativas=150_000)  # +150%
        with pytest.raises(SanityCheckError, match="[Vv]aria"):
            validate_metrics(current, thresholds, previous=previous)


class TestReductionSummary:
    def test_computes_percentages_for_each_stage(self):
        summary = reduction_summary(_metrics())
        assert "scanned_to_target" in summary
        assert "target_to_ativas" in summary
        assert "ativas_to_consolidated" in summary

    def test_handles_zero_denominator_gracefully(self):
        summary = reduction_summary(_metrics(total_estabelecimentos_scanned=0))
        assert summary["scanned_to_target"] == "n/a"
