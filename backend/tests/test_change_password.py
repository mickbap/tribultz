"""Troca de senha pelo usuário autenticado (#lacuna do onboarding Founding Partners).

Contas provisionadas pelo Command Center nascem com senha definida por TERCEIRO —
o Owner — e não havia como o titular trocá-la de dentro da plataforma. A única
saída era sair e usar "Esqueci minha senha". Para uma consultoria recebendo
acesso, trocar a senha inicial é a primeira coisa que se tenta fazer.

Fixtures replicadas de test_auth.py, que as define localmente (não há conftest
com elas).
"""

import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.core.security import get_password_hash, verify_password

# Use the environment variable for DB connection (standard for CI/Docker)
# Fallback to localhost for local dev if not set, but CI should set it.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module")
def db_engine():
    # Setup: ensure tables exist (if not using migration yet)
    # Ideally CI runs migrations before tests. For now we assume or create.
    # Base.metadata.create_all(bind=engine) # Dangerous on prod, okay on CI if fresh.
    # Better: Assume environment is prepped or use a separate test DB.
    # Given instructions "Use Postgres integration tests (docker/CI)", we assume the DB is ready.
    yield engine
    # Teardown if needed


@pytest.fixture(name="session")
def session_fixture(db_engine):
    """
    Creates a new database session for a test.
    We roll back the transaction after the test to keep the DB clean.
    """
    connection = db_engine.connect()
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


@pytest.fixture
def test_tenant(session):
    # Use a random slug to avoid collision if rollback fails or parallel runs
    import uuid
    slug = f"test-tenant-{uuid.uuid4()}"
    tenant = Tenant(name="Test Tenant", slug=slug)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


@pytest.fixture
def test_user(session, test_tenant):
    import uuid
    email = f"user-{uuid.uuid4()}@test.com"
    user = User(
        email=email,
        full_name="Test User",
        password_hash=get_password_hash("password123"),
        tenant_id=test_tenant.id,
        role="admin",
        email_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Clear rate-limiter state so repeated pytest runs (QA Gates) don't 429."""
    from app.routers.auth import _login_limiter, _register_limiter, _forgot_limiter

    prefixes = ["ratelimit:login:", "ratelimit:register:", "ratelimit:resend:", "ratelimit:forgot:"]
    for rl in (_login_limiter, _register_limiter, _forgot_limiter):
        rl._memory_store.clear()

    redis_conn = _login_limiter.redis
    if redis_conn is not None:
        for prefix in prefixes:
            # Delete the specific key that testclient uses (IP "testclient")
            redis_conn.delete(f"{prefix}testclient")
            redis_conn.delete(f"{prefix}127.0.0.1")
            redis_conn.delete(f"{prefix}unknown")



# ── Tests ─────────────────────────────────────────────────────

SENHA_INICIAL = "senha-do-owner-123"
SENHA_NOVA = "nova-senha-forte-1"


@pytest.fixture
def fp_user(session, test_tenant):
    """Conta como o Command Center a cria: senha definida pelo OWNER, e-mail já verificado."""
    import uuid
    user = User(
        email=f"fp-{uuid.uuid4()}@test.com",
        full_name="Consultoria",
        password_hash=get_password_hash(SENHA_INICIAL),
        tenant_id=test_tenant.id,
        account_type="contador",
        role="contador",
        email_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _login(client, email, senha):
    return client.post("/api/v1/auth/login", json={"email": email, "password": senha})


def _auth(client, email, senha):
    r = _login(client, email, senha)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_troca_senha_com_senha_atual_correta(client, fp_user, session):
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": SENHA_INICIAL, "new_password": SENHA_NOVA},
        headers=_auth(client, fp_user.email, SENHA_INICIAL),
    )
    assert r.status_code == 200, r.text
    session.refresh(fp_user)
    assert verify_password(SENHA_NOVA, fp_user.password_hash)
    assert not verify_password(SENHA_INICIAL, fp_user.password_hash)


def test_senha_atual_errada_e_recusada(client, fp_user, session):
    """Sem exigir a senha atual, um token vazado tomaria a conta em definitivo."""
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "chute-errado", "new_password": SENHA_NOVA},
        headers=_auth(client, fp_user.email, SENHA_INICIAL),
    )
    assert r.status_code == 400
    session.refresh(fp_user)
    assert verify_password(SENHA_INICIAL, fp_user.password_hash), "senha não podia mudar"


def test_nova_senha_curta_e_recusada(client, fp_user):
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": SENHA_INICIAL, "new_password": "curta"},
        headers=_auth(client, fp_user.email, SENHA_INICIAL),
    )
    assert r.status_code == 400


def test_nova_senha_igual_a_atual_e_recusada(client, fp_user):
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": SENHA_INICIAL, "new_password": SENHA_INICIAL},
        headers=_auth(client, fp_user.email, SENHA_INICIAL),
    )
    assert r.status_code == 400


def test_sem_autenticacao_e_recusado(client):
    r = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "x", "new_password": SENHA_NOVA},
    )
    assert r.status_code == 401


def test_login_passa_a_usar_a_senha_nova(client, fp_user):
    client.post(
        "/api/v1/auth/change-password",
        json={"current_password": SENHA_INICIAL, "new_password": SENHA_NOVA},
        headers=_auth(client, fp_user.email, SENHA_INICIAL),
    )
    assert _login(client, fp_user.email, SENHA_INICIAL).status_code == 401
    assert _login(client, fp_user.email, SENHA_NOVA).status_code == 200
