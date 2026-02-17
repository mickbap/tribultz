import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
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
        role="admin"
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


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
    assert response.json()["detail"] == "Incorrect email or password"


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
    assert response.json()["detail"] == "Inactive user"


def test_login_wrong_tenant(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user.email,
            "password": "password123",
            "tenant_slug": "non-existent-tenant"
        }
    )
    assert response.status_code == 401
