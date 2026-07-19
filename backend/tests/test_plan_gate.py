"""Plan Gate — Grant Adapter aware (#487).

`require_plan`/`check_usage_limit`/`get_plan_slug` devem reconhecer um Grant
ativo (ADR-0008) com a mesma precedência já usada no login (`auth.py`) — sem
isso, um Early Adopter com Grant (sem Subscription — RNF002) sempre recebia
403 em qualquer endpoint gated, apesar do JWT reportar o plano correto.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.plan_gate import check_usage_limit, get_plan_slug, require_plan
from app.core.security import get_password_hash
from app.models.auth import Tenant, User
from app.models.billing import Plan, Subscription
from app.models.founding_partner import EarlyAdopter, EarlyGrant

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")


def _pg_available() -> bool:
    try:
        with create_engine(DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Postgres indisponível (roda no CI)")

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _tenant_and_user(session, email: str) -> tuple[Tenant, User]:
    tenant = Tenant(name="Empresa Teste", slug=f"t-{uuid.uuid4().hex[:10]}")
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id, email=email, full_name="Teste",
        password_hash=get_password_hash("x"), email_verified=True,
    )
    session.add(user)
    session.flush()
    return tenant, user


def _add_subscription(session, tenant: Tenant, user: User, plan_slug: str) -> None:
    plan = session.execute(select(Plan).where(Plan.slug == plan_slug)).scalar_one()
    session.add(Subscription(tenant_id=tenant.id, user_id=user.id, plan_id=plan.id, status="active"))
    session.flush()


def _add_grant(session, tenant: Tenant, plan_slug: str = "contador") -> None:
    ea = EarlyAdopter(tenant_id=tenant.id, empresa="Empresa Teste", email="ea@teste.com")
    session.add(ea)
    session.flush()
    hoje = date.today()
    session.add(EarlyGrant(
        early_adopter_id=ea.id, tenant_id=tenant.id, plan_slug=plan_slug,
        starts_at=hoje - timedelta(days=1), ends_at=hoje + timedelta(days=30),
        status="active",
    ))
    session.flush()


def test_early_adopter_com_grant_ativo_acessa_endpoint_gated_sem_subscription(session):
    """Núcleo do #487: Grant ativo, ZERO Subscription — antes retornava 403 sempre."""
    tenant, user = _tenant_and_user(session, f"ea-{uuid.uuid4().hex[:8]}@empresa.com")
    _add_grant(session, tenant, plan_slug="contador")

    check = require_plan("contador", "empresarial", "profissional")
    result = check(current_user=user, db=session)  # não levanta HTTPException
    assert result is user


def test_early_adopter_com_grant_bloqueado_fora_do_plano_do_grant(session):
    tenant, user = _tenant_and_user(session, f"ea-{uuid.uuid4().hex[:8]}@empresa.com")
    _add_grant(session, tenant, plan_slug="starter")  # fora dos planos aceitos abaixo

    check = require_plan("contador", "empresarial", "profissional")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        check(current_user=user, db=session)
    assert exc.value.status_code == 403


def test_usuario_pagante_sem_grant_continua_funcionando(session):
    """Regressão: só Subscription, sem Grant — comportamento pré-existente intacto."""
    tenant, user = _tenant_and_user(session, f"pay-{uuid.uuid4().hex[:8]}@empresa.com")
    _add_subscription(session, tenant, user, plan_slug="profissional")

    check = require_plan("contador", "empresarial", "profissional")
    assert check(current_user=user, db=session) is user


def test_grant_tem_precedencia_sobre_subscription(session):
    """Mesma precedência do login (ADR-0008): Grant ativo > assinatura."""
    tenant, user = _tenant_and_user(session, f"both-{uuid.uuid4().hex[:8]}@empresa.com")
    _add_subscription(session, tenant, user, plan_slug="starter")
    _add_grant(session, tenant, plan_slug="contador")

    assert get_plan_slug(session, user) == "contador"


def test_sem_grant_e_sem_subscription_bloqueado(session):
    _tenant, user = _tenant_and_user(session, f"none-{uuid.uuid4().hex[:8]}@empresa.com")

    check = require_plan("contador", "empresarial", "profissional")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        check(current_user=user, db=session)
    assert exc.value.status_code == 403


def test_check_usage_limit_reconhece_grant():
    """check_usage_limit também deve resolver o Plan via Grant (max_validations etc.)."""
    engine2 = create_engine(DATABASE_URL)
    Session2 = sessionmaker(autocommit=False, autoflush=False, bind=engine2)
    conn = engine2.connect()
    txn = conn.begin()
    session = Session2(bind=conn)
    try:
        tenant, user = _tenant_and_user(session, f"usage-{uuid.uuid4().hex[:8]}@empresa.com")
        _add_grant(session, tenant, plan_slug="contador")  # ilimitado (max_validations=None)

        check = check_usage_limit("validations")
        assert check(current_user=user, db=session) is user
    finally:
        session.close()
        txn.rollback()
        conn.close()


def test_actor_partner_sem_tenant_nao_quebra(session):
    """Ator partner (RFC-0026) não tem tenant_id — _get_effective_plan não deve
    tentar resolver Grant (que exige tenant_id) e deve só refletir a ausência
    de plano, sem lançar exceção inesperada."""
    from app.models.partner import Partner

    partner = Partner(name="Parceiro Teste", code=f"TEST{uuid.uuid4().hex[:6].upper()}")
    session.add(partner)
    session.flush()
    user = User(
        partner_id=partner.id, email=f"partner-{uuid.uuid4().hex[:8]}@teste.com",
        full_name="Ator Partner", password_hash=get_password_hash("x"), email_verified=True,
        role="partner",
    )
    session.add(user)
    session.flush()

    assert get_plan_slug(session, user) is None
