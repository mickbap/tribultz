import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User, UserTenant
from app.core.security import get_password_hash

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

def test_login_success(client, test_user, test_tenant):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
            "tenant_slug": test_tenant.slug
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_response_body_includes_role_and_tenant(client, test_user, test_tenant):
    """Regressão: response_model=Token só declarava access_token/token_type e
    descartava silenciosamente role/tenant_id/tenants — o handler retornava
    esses campos, mas o FastAPI filtrava tudo que não estava no schema. Isso
    quebrava toda UI client-side que lê o corpo do /login (link Admin,
    redirect de superadmin, nome do tenant ativo) mesmo com o JWT correto."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
            "tenant_slug": test_tenant.slug
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "admin"
    assert data["tenant_id"] == str(test_tenant.id)
    assert data["account_type"] == "empresa"
    assert "tenants" in data  # test_user não tem linha em user_tenants; lista vazia é válida aqui


def test_switch_tenant_response_includes_role_for_new_tenant(client, session, test_user, test_tenant):
    """Regressão: /switch-tenant nunca devolvia role/account_type no corpo —
    o frontend (Topbar.tsx) só atualizava tenant_id/token e dava reload, então
    um usuário com role diferente em cada tenant (comum: admin numa empresa,
    contador levado por /settings noutra) ficava com o role antigo em cache
    até fazer logout/login de novo."""
    other_tenant = Tenant(name="Outro Tenant", slug=f"other-{test_tenant.slug}")
    session.add(other_tenant)
    session.flush()
    session.add_all([
        UserTenant(user_id=test_user.id, tenant_id=test_tenant.id, role="admin", is_default=True),
        UserTenant(user_id=test_user.id, tenant_id=other_tenant.id, role="contador", is_default=False),
    ])
    session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "password123", "tenant_slug": test_tenant.slug},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/auth/switch-tenant",
        json={"tenant_id": str(other_tenant.id)},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "contador"  # role do vínculo com other_tenant, não o role original
    assert data["account_type"] == "empresa"
    assert data["tenant_name"] == "Outro Tenant"


def test_login_wrong_password(client, test_user, test_tenant):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "wrongpassword",
            "tenant_slug": test_tenant.slug
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha incorretos"


def test_login_inactive_user(client, session, test_user, test_tenant):
    test_user.is_active = False
    session.add(test_user)
    session.commit()
    
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
            "tenant_slug": test_tenant.slug
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Usuário inativo"


def test_login_nonexistent_email(client, test_user):
    """Login with email that does not exist returns 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "password123",
            "tenant_slug": "any-tenant"
        }
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Email ou senha incorretos"


# ── /add-cnpj — limite numérico por plano (Escopo 3.5 do go-live de billing) ──


def _contador_with_plan(session, plan_slug: str):
    """Cria um usuário account_type=contador com assinatura no plano informado
    e 1 UserTenant já existente (o próprio tenant, is_default=True) — estado
    real de qualquer conta contador recém-criada."""
    import uuid
    from app.models.billing import Plan, Subscription

    tenant = Tenant(name="Escritório Contábil Teste", slug=f"contador-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"contador-{uuid.uuid4()}@test.com",
        full_name="Contador Teste",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="contador",
        account_type="contador",
        email_verified=True,
    )
    session.add(user)
    session.flush()

    session.add(UserTenant(user_id=user.id, tenant_id=tenant.id, role="contador", is_default=True))

    plan = session.execute(select(Plan).where(Plan.slug == plan_slug)).scalar_one()
    session.add(Subscription(
        tenant_id=tenant.id, user_id=user.id, plan_id=plan.id, status="active",
    ))
    session.commit()
    session.refresh(user)
    return user, tenant


def test_add_cnpj_blocks_when_plan_limit_reached(client, session):
    """Plano Profissional (max_cnpj=1): usuário já tem 1 CNPJ (o próprio) —
    /add-cnpj deve bloquear com 403 antes de chamar a Receita Federal."""
    user, tenant = _contador_with_plan(session, "profissional")

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123", "tenant_slug": tenant.slug},
    )
    assert login.status_code == 200

    response = client.post(
        "/api/v1/auth/add-cnpj",
        json={"cnpj": "11222333000181"},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert response.status_code == 403
    assert "Limite" in response.json()["detail"]


def test_add_cnpj_allows_when_under_plan_limit(client, session):
    """Plano Empresarial (max_cnpj=10): usuário com 1 CNPJ ainda tem margem —
    /add-cnpj deve passar da checagem de limite (chega a validar o CNPJ)."""
    from unittest.mock import AsyncMock, patch
    from app.services.cnpj_validator import CnpjResult

    user, tenant = _contador_with_plan(session, "empresarial")

    login = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123", "tenant_slug": tenant.slug},
    )
    assert login.status_code == 200

    mock_result = CnpjResult(
        valid=True, cnpj="11222333000181", company_name="Cliente Teste Ltda",
        status="ATIVA", error="",
    )
    with patch("app.routers.auth.validate_cnpj", new=AsyncMock(return_value=mock_result)):
        response = client.post(
            "/api/v1/auth/add-cnpj",
            json={"cnpj": "11222333000181"},
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
    assert response.status_code == 200
