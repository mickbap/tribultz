from datetime import date

from app.services.rule_enforcement import resolve_rule_enforcement


def test_estados_nao_sao_inferidos_da_producao():
    state = resolve_rule_enforcement(
        "NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", date(2026, 7, 15)
    )

    assert state is not None
    assert state["schema_supported"] is True
    assert state["validation_rule_defined"] is True
    assert state["homologation_enforced"] is True
    assert state["legal_required"] is False
    assert state["production_enforced"] is False


def test_vigencia_altera_apenas_os_estados_com_marco():
    state = resolve_rule_enforcement(
        "NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", date(2026, 8, 3)
    )

    assert state is not None
    assert state["legal_required"] is True
    assert state["production_enforced"] is True
    assert state["effective_from"]["schema_supported"] is None


def test_chave_exata_nao_vaza_para_outro_documento_ou_versao():
    assert resolve_rule_enforcement(
        "NFCE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.00", date(2026, 8, 3)
    ) is None
    assert resolve_rule_enforcement(
        "NFE", "DANFE_SIMPLIFICADO_RESTRICAO", "1.10a", date(2026, 8, 3)
    ) is None
