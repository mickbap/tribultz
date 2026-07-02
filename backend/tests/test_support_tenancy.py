"""#411: isolamento de tenant e papéis no /api/v1/support.

Bug auditado em 02/07/2026: `update_ticket_status` aceitava role "admin"
(papel default de todo primeiro usuário de tenant) como se fosse staff
Tribultz e não validava tenant — admin do tenant B podia alterar status de
ticket do tenant A. `add_message` marcava admins de tenant como is_staff.

Padrão de auth: override de get_current_user (idêntico a test_exceptions.py).
DB real (Postgres do testcontainer) com transaction rollback por teste.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.support import SupportTicket

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


def _make_user(session, role: str = "admin") -> User:
    tenant = Tenant(name=f"Tenant {uuid.uuid4().hex[:6]}", slug=f"tenant-{uuid.uuid4()}")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    user = User(
        email=f"user-{uuid.uuid4()}@tribultz.com",
        full_name="Usuário Teste",
        password_hash="hashed",
        tenant_id=tenant.id,
        role=role,
        email_verified=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _make_ticket(session, owner: User) -> SupportTicket:
    ticket = SupportTicket(
        tenant_id=owner.tenant_id,
        user_id=owner.id,
        title="Erro na validação",
        description="Detalhe do problema.",
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


@pytest.fixture(name="owner_a")
def owner_a_fixture(session):
    return _make_user(session, role="admin")


@pytest.fixture(name="admin_b")
def admin_b_fixture(session):
    """Admin de OUTRO tenant — não pode tocar em nada do tenant A."""
    return _make_user(session, role="admin")


@pytest.fixture(name="superadmin")
def superadmin_fixture(session):
    return _make_user(session, role="superadmin")


def _client_as(session, user: User) -> TestClient:
    def override_get_db():
        yield session

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


# ── update_ticket_status: papéis e tenant ─────────────────────────────────


def test_admin_de_outro_tenant_nao_altera_status(session, owner_a, admin_b):
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, admin_b)
    resp = client.patch(f"/api/v1/support/tickets/{ticket.id}/status", json={"status": "closed"})
    assert resp.status_code == 403, resp.text
    session.refresh(ticket)
    assert str(ticket.status) == "open"


def test_admin_do_proprio_tenant_nao_e_staff_para_status(session, owner_a):
    """Role 'admin' é admin do TENANT, não equipe Tribultz — endpoint é staff-only."""
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, owner_a)
    resp = client.patch(f"/api/v1/support/tickets/{ticket.id}/status", json={"status": "closed"})
    assert resp.status_code == 403, resp.text


def test_superadmin_altera_status_de_qualquer_tenant(session, owner_a, superadmin):
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, superadmin)
    resp = client.patch(f"/api/v1/support/tickets/{ticket.id}/status", json={"status": "in_progress"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "in_progress"


# ── add_message: is_staff reservado a superadmin ──────────────────────────


def test_admin_de_tenant_nao_e_is_staff_na_mensagem(session, owner_a):
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, owner_a)
    resp = client.post(f"/api/v1/support/tickets/{ticket.id}/messages", json={"body": "Alguma novidade?"})
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_staff"] is False


def test_superadmin_e_is_staff_na_mensagem(session, owner_a, superadmin):
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, superadmin)
    resp = client.post(f"/api/v1/support/tickets/{ticket.id}/messages", json={"body": "Estamos analisando."})
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_staff"] is True


# ── sanidade: leitura cross-tenant continua bloqueada ─────────────────────


def test_leitura_cross_tenant_segue_404(session, owner_a, admin_b):
    ticket = _make_ticket(session, owner_a)
    client = _client_as(session, admin_b)
    assert client.get(f"/api/v1/support/tickets/{ticket.id}").status_code == 404
    assert client.get(f"/api/v1/support/tickets/{ticket.id}/messages").status_code == 404
