"""Grant Adapter — vigência e status efetivo (ADR-0008). Sem DB.

"Grant ativo = status ativo E hoje ∈ [starts_at, ends_at]" — expiração lazy.
"""

from datetime import datetime, timedelta, timezone

from app.models.founding_partner import (
    EarlyGrant,
    effective_grant_status,
    grant_is_active,
)

NOW = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)


def _grant(status="active", start_delta=-1, end_delta=+1) -> EarlyGrant:
    return EarlyGrant(
        status=status,
        starts_at=NOW + timedelta(days=start_delta),
        ends_at=NOW + timedelta(days=end_delta),
        plan_slug="contador",
    )


def test_grant_ativo_dentro_da_janela():
    assert grant_is_active(_grant(), NOW) is True


def test_grant_expirado_nao_e_ativo():
    # ends_at no passado — a expiração encerra o acesso sozinha (sem beat).
    assert grant_is_active(_grant(start_delta=-10, end_delta=-1), NOW) is False


def test_grant_futuro_nao_e_ativo():
    assert grant_is_active(_grant(start_delta=+1, end_delta=+10), NOW) is False


def test_grant_revogado_nunca_e_ativo():
    assert grant_is_active(_grant(status="revoked"), NOW) is False


def test_status_efetivo_vencido_vira_expired():
    # status 'active' no banco, mas fora da janela → exibe 'expired'.
    assert effective_grant_status(_grant(start_delta=-10, end_delta=-1), NOW) == "expired"


def test_status_efetivo_ativo_permanece_active():
    assert effective_grant_status(_grant(), NOW) == "active"


def test_status_efetivo_revogado_permanece_revoked():
    assert effective_grant_status(_grant(status="revoked"), NOW) == "revoked"


def test_borda_inclusiva_no_inicio_e_fim():
    g = EarlyGrant(status="active", starts_at=NOW, ends_at=NOW, plan_slug="contador")
    assert grant_is_active(g, NOW) is True  # janela inclusiva nas duas pontas
