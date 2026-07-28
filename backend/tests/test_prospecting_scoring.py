"""Pré-score determinístico compute_score() (PO-2026-07-SALES-001, Fase 1) — puro, sem DB."""

from datetime import date
from decimal import Decimal

import pytest
import yaml

from app.services.prospecting.rubric_loader import load_rubric
from app.services.prospecting.scoring import ScoreInput, compute_score

RUBRIC = load_rubric(version="v1")
TODAY = date(2026, 7, 28)

# Rubrica sintética com penalidade de MEI fraca (-5 em vez de -100 da v1 real) —
# usada só para provar que o cap de tier é aplicado pelo CÓDIGO (scoring.py),
# não apenas pela aritmética dos pesos. Com a v1 real o MEI já cai pra D pela
# soma dos pesos, o que não exercitaria de fato o guard.
_WEAK_MEI_PENALTY_RUBRIC_YAML = {
    "version": "vTest-weak-mei",
    "base_score": 50,
    "tiers": {"A": {"min": 80}, "B": {"min": 60}, "C": {"min": 40}, "D": {"min": 0}},
    "scoring": {
        "socios": {"1": 10, "2": 10, "3_or_more": 10},
        "porte": {"mei": -5, "00": 10, "01": 10, "03": 10, "05": 10},
        "capital_social": {"faixas": [{"acima": 0, "peso": 10}]},
        "idade_anos": {"faixas": [{"acima": 0, "peso": 10}]},
        "email_domain_category": {"default": 10},
        "estabelecimentos": {"default": 10},
        "geografia": {"default": 10},
    },
}


def _base_input(
    *,
    qtd_socios: int = 2,
    porte: str = "05",
    opcao_mei: bool = False,
    capital_social: Decimal = Decimal("100000"),
    data_inicio_atividade: date | None = date(2015, 1, 1),  # ~11 anos
    email_domain_category: str = "dominio_nominal",
    qtd_estabelecimentos: int = 3,
    uf: str = "RS",
    razao_social: str = "Escritório Modelo Contabilidade Ltda",
    as_of: date = TODAY,
) -> ScoreInput:
    return ScoreInput(
        qtd_socios=qtd_socios,
        porte=porte,
        opcao_mei=opcao_mei,
        capital_social=capital_social,
        data_inicio_atividade=data_inicio_atividade,
        email_domain_category=email_domain_category,
        qtd_estabelecimentos=qtd_estabelecimentos,
        uf=uf,
        razao_social=razao_social,
        as_of=as_of,
    )


class TestComputeScoreBasics:
    def test_strong_profile_lands_in_tier_a(self):
        result = compute_score(_base_input(), RUBRIC)
        assert result.tier == "A"
        assert 0 <= result.score <= 100
        assert result.rubric_version == "v1"
        assert result.justification  # não vazio

    def test_score_is_clamped_to_0_100(self):
        # Perfil pior possível: sem e-mail, MEI, sócio único, recém-aberta.
        weak = _base_input(
            qtd_socios=1, opcao_mei=True, capital_social=Decimal("0"),
            data_inicio_atividade=TODAY, email_domain_category="ausente",
            qtd_estabelecimentos=1, uf="AM",
        )
        result = compute_score(weak, RUBRIC)
        assert result.score == 0


class TestMeiCapInvariant:
    """Critério de aceite: nenhum Tier A pode ser MEI — mesmo se um perfil MEI
    tivesse todos os outros sinais positivos ao extremo."""

    def test_mei_never_reaches_tier_a_even_with_otherwise_ideal_profile(self):
        mei_but_ideal = _base_input(
            opcao_mei=True, qtd_socios=5, capital_social=Decimal("500000"),
            data_inicio_atividade=date(2000, 1, 1), qtd_estabelecimentos=10,
            email_domain_category="dominio_nominal", uf="RS",
        )
        result = compute_score(mei_but_ideal, RUBRIC)
        assert result.tier in ("B", "C", "D")
        assert result.tier != "A"

    def test_code_level_guard_caps_tier_even_when_rubric_weights_would_reach_a(self, tmp_path):
        """Prova que o cap é aplicado pelo código, não pela aritmética: com uma
        rubrica cujo peso de MEI é fraco (-5), a soma bruta chegaria à Tier A
        (raw=105 -> clamp 100) — o guard em scoring.py precisa rebaixar para B
        mesmo assim."""
        weak_rubric_path = tmp_path / "rubric_weak_mei.yaml"
        weak_rubric_path.write_text(yaml.safe_dump(_WEAK_MEI_PENALTY_RUBRIC_YAML))
        weak_rubric = load_rubric(path=weak_rubric_path)

        result = compute_score(_base_input(opcao_mei=True), weak_rubric)
        assert result.tier == "B"

    def test_non_mei_ideal_profile_can_reach_tier_a(self):
        ideal = _base_input(
            opcao_mei=False, porte="05", qtd_socios=5, capital_social=Decimal("500000"),
            data_inicio_atividade=date(2000, 1, 1), qtd_estabelecimentos=10,
            email_domain_category="dominio_nominal", uf="RS",
        )
        result = compute_score(ideal, RUBRIC)
        assert result.tier == "A"


class TestBreakdownAndJustification:
    def test_breakdown_has_all_six_dimensions(self):
        result = compute_score(_base_input(), RUBRIC)
        assert set(result.breakdown) == {
            "socios", "porte", "capital_social", "idade_anos",
            "email_domain_category", "estabelecimentos", "geografia",
        }

    def test_justification_mentions_mei_when_applicable(self):
        result = compute_score(_base_input(opcao_mei=True), RUBRIC)
        assert "MEI" in result.justification

    def test_justification_mentions_own_domain_when_nominal(self):
        result = compute_score(_base_input(email_domain_category="dominio_nominal"), RUBRIC)
        assert "domínio de e-mail próprio" in result.justification.lower() or "domínio" in result.justification.lower()


@pytest.mark.parametrize(
    "qtd_socios,expected_key_weight",
    [(1, "1"), (2, "2"), (3, "3_or_more"), (10, "3_or_more")],
)
def test_socios_bucketing_matches_rubric_keys(qtd_socios, expected_key_weight):
    result = compute_score(_base_input(qtd_socios=qtd_socios), RUBRIC)
    assert result.breakdown["socios"] == RUBRIC.get_weight("socios", expected_key_weight)
