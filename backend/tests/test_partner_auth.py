"""Modelo de Ator (RFC-0026) — Partner como ator autenticável.

Cobre: login do parceiro (sem crash no fluxo tenant-only), isolamento
cruzado (partner não acessa rota tenant-scoped e vice-versa), e a
CHECK constraint que garante tenant_id XOR partner_id no banco.
"""
import os
import uuid

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_partner, get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.partner import Partner

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")

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


@pytest.fixture(name="client")
def client_fixture(session):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    from app.routers.auth import _login_limiter, _register_limiter, _forgot_limiter

    prefixes = ["ratelimit:login:", "ratelimit:register:", "ratelimit:resend:", "ratelimit:forgot:"]
    for rl in (_login_limiter, _register_limiter, _forgot_limiter):
        rl._memory_store.clear()
    redis_conn = _login_limiter.redis
    if redis_conn is not None:
        for prefix in prefixes:
            redis_conn.delete(f"{prefix}testclient")
            redis_conn.delete(f"{prefix}127.0.0.1")
            redis_conn.delete(f"{prefix}unknown")


@pytest.fixture
def test_tenant(session):
    tenant = Tenant(name="Test Tenant", slug=f"test-tenant-{uuid.uuid4()}")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@pytest.fixture
def test_tenant_user(session, test_tenant):
    user = User(
        email=f"user-{uuid.uuid4()}@test.com",
        full_name="Test Tenant User",
        password_hash=get_password_hash("password123"),
        tenant_id=test_tenant.id,
        role="admin",
        email_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def test_partner(session):
    partner = Partner(type="accountant", name="Dra. Kátia Pollon", code=f"KATIA{uuid.uuid4().hex[:6].upper()}")
    session.add(partner)
    session.commit()
    session.refresh(partner)
    return partner


@pytest.fixture
def test_partner_user(session, test_partner):
    user = User(
        email=f"partner-{uuid.uuid4()}@test.com",
        full_name="Dra. Kátia Pollon",
        password_hash=get_password_hash("password123"),
        partner_id=test_partner.id,
        role="partner",
        email_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# ── actor_type ────────────────────────────────────────────────

def test_actor_type_tenant(test_tenant_user):
    assert test_tenant_user.actor_type == "tenant"


def test_actor_type_partner(test_partner_user):
    assert test_partner_user.actor_type == "partner"


# ── CHECK constraint (banco) ─────────────────────────────────

def test_user_requires_exactly_one_actor_domain(session, test_tenant, test_partner):
    """Nem os dois, nem nenhum — a integridade é estrutural, não só de código."""
    both = User(
        email=f"both-{uuid.uuid4()}@test.com",
        full_name="Invalid",
        password_hash=get_password_hash("x"),
        tenant_id=test_tenant.id,
        partner_id=test_partner.id,
        role="user",
    )
    session.add(both)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    neither = User(
        email=f"neither-{uuid.uuid4()}@test.com",
        full_name="Invalid",
        password_hash=get_password_hash("x"),
        role="user",
    )
    session.add(neither)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_partner_email_uniqueness_enforced(session, test_partner):
    """A constraint (tenant_id, email) não pega duplicidade com tenant_id NULL —
    o índice único parcial precisa cobrir isso."""
    email = f"dup-{uuid.uuid4()}@test.com"
    session.add(User(
        email=email, full_name="A", password_hash=get_password_hash("x"),
        partner_id=test_partner.id, role="partner",
    ))
    session.commit()

    session.add(User(
        email=email, full_name="B", password_hash=get_password_hash("x"),
        partner_id=test_partner.id, role="partner",
    ))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ── Login ────────────────────────────────────────────────────

def _decode(token: str) -> dict:
    """response_model=Token filtra o corpo HTTP — os claims reais só existem
    dentro do JWT. Decodificar é a única forma correta de verificá-los."""
    from jose import jwt

    from app.config import settings

    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])


def test_login_partner_success(client, test_partner_user, test_partner):
    """Não deve crashar tentando resolver tenant/billing/Grant (que não existem)."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_partner_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    claims = _decode(response.json()["access_token"])
    assert claims["actor_type"] == "partner"
    assert claims["partner_id"] == str(test_partner.id)
    assert claims["role"] == "partner"
    assert claims.get("tenant_id") is None


def test_login_tenant_still_works(client, test_tenant_user, test_tenant):
    """Regressão — fluxo tenant existente inalterado."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": test_tenant_user.email, "password": "password123"},
    )
    assert response.status_code == 200
    claims = _decode(response.json()["access_token"])
    assert claims["actor_type"] == "tenant"
    assert claims["tenant_id"] == str(test_tenant.id)


# ── Isolamento cruzado ───────────────────────────────────────
# Exercita get_current_user/get_current_partner diretamente (nível de
# dependência), sem depender de rotas de sondagem montadas no app real.

async def test_partner_actor_rejected_by_get_current_user(test_partner_user):
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(actor=test_partner_user)
    assert exc_info.value.status_code == 403


async def test_tenant_actor_rejected_by_get_current_partner(test_tenant_user):
    with pytest.raises(HTTPException) as exc_info:
        await get_current_partner(actor=test_tenant_user)
    assert exc_info.value.status_code == 403


async def test_tenant_actor_accepted_by_get_current_user(test_tenant_user):
    result = await get_current_user(actor=test_tenant_user)
    assert result is test_tenant_user


async def test_partner_actor_accepted_by_get_current_partner(test_partner_user):
    result = await get_current_partner(actor=test_partner_user)
    assert result is test_partner_user
