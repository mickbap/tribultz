"""Carregamento/validação da rubrica YAML (PO-2026-07-SALES-001, Fase 1) — puro, sem DB."""

import pytest
import yaml

from app.services.prospecting.rubric_loader import (
    RubricValidationError,
    load_rubric,
)


class TestLoadRealRubricV1:
    def test_loads_and_exposes_required_fields(self):
        rubric = load_rubric(version="v1")
        assert rubric.version == "v1"
        assert rubric.base_score == 50
        assert set(rubric.tiers) == {"A", "B", "C", "D"}
        assert len(rubric.checksum) == 64  # sha256 hex

    def test_checksum_is_stable_across_loads(self):
        r1 = load_rubric(version="v1")
        r2 = load_rubric(version="v1")
        assert r1.checksum == r2.checksum

    def test_get_weight_falls_back_to_default(self):
        rubric = load_rubric(version="v1")
        # UF não listada explicitamente na rubrica v1 -> cai no "default": 0
        assert rubric.get_weight("geografia", "AM") == 0
        assert rubric.get_weight("geografia", "RS") == 10

    def test_get_weight_returns_zero_when_no_default_and_key_missing(self):
        rubric = load_rubric(version="v1")
        assert rubric.get_weight("socios", "999_nao_existe") == 0

    def test_tier_for_score_picks_highest_matching_tier(self):
        rubric = load_rubric(version="v1")
        assert rubric.tier_for_score(85) == "A"
        assert rubric.tier_for_score(80) == "A"
        assert rubric.tier_for_score(79) == "B"
        assert rubric.tier_for_score(60) == "B"
        assert rubric.tier_for_score(40) == "C"
        assert rubric.tier_for_score(0) == "D"


class TestLoadRubricValidation:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(RubricValidationError):
            load_rubric(path=tmp_path / "does_not_exist.yaml")

    def test_missing_top_level_key_raises(self, tmp_path):
        bad = tmp_path / "bad_rubric.yaml"
        bad.write_text(yaml.safe_dump({"version": "vX", "base_score": 50}))
        with pytest.raises(RubricValidationError, match="tiers"):
            load_rubric(path=bad)

    def test_missing_scoring_dimension_raises(self, tmp_path):
        bad = tmp_path / "bad_rubric.yaml"
        bad.write_text(yaml.safe_dump({
            "version": "vX",
            "base_score": 50,
            "tiers": {"A": {"min": 80}, "D": {"min": 0}},
            "scoring": {"socios": {"1": 1}},
        }))
        with pytest.raises(RubricValidationError, match="porte"):
            load_rubric(path=bad)

    def test_no_version_and_no_path_raises(self):
        with pytest.raises(RubricValidationError):
            load_rubric()
