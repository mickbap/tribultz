"""Integration tests for /api/v1/exceptions — CRUD + decision flow.

Padrão de auth: override de get_current_user (idêntico a tests/api/test_tasks_async.py).
DB real (Postgres do testcontainer) com transaction rollback por teste.
"""

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User

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


@pytest.fixture(name="auth_user")
def auth_user_fixture(session):
    """Cria tenant + user real no banco de teste."""
    slug = f"tenant-{uuid.uuid4()}"
    tenant = Tenant(name="Tribultz Test", slug=slug)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    email = f"op-{uuid.uuid4()}@tribultz.com"
    user = User(
        email=email,
        full_name="Operador Teste",
        password_hash="hashed",
        tenant_id=tenant.id,
        role="admin",
        email_verified=True,
        phone="11 99999-0000",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="client")
def client_fixture(session, auth_user):
    def override_get_db():
        yield session

    def override_get_current_user():
        return auth_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────


def test_create_exception_persists_and_dispatches_email(client, auth_user, session):
    payload = {
        "finding_id": "F_CST_LEN",
        "rule_id": "CST_3_DIGITS",
        "justification": "Item em regime monofásico — CST não se aplica.",
        "admin_name": "Roberta Admin",
        "admin_email": "roberta@cliente.com",
    }
    with patch("app.routers.exceptions.send_exception_notification_email") as mock_send:
        mock_send.return_value = True
        resp = client.post("/api/v1/exceptions", json=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "OPEN"
    assert body["admin_name"] == "Roberta Admin"
    assert body["admin_email"] == "roberta@cliente.com"
    assert body["created_by"] == auth_user.email
    assert body["finding_id"] == "F_CST_LEN"
    # E-mail dispatched via BackgroundTasks — TestClient runs them after response
    assert mock_send.called
    args = mock_send.call_args.kwargs
    assert args["to_email"] == "roberta@cliente.com"
    assert args["operator_email"] == auth_user.email
    assert args["operator_phone"] == "11 99999-0000"

    # Confirma persistência no banco
    session.expire_all()
    row = session.execute(
        text("SELECT status, admin_email FROM exception_requests WHERE id = :id"),
        {"id": body["id"]},
    ).fetchone()
    assert row is not None
    assert row.status == "OPEN"
    assert row.admin_email == "roberta@cliente.com"


def test_create_exception_with_invalid_email_returns_422(client):
    resp = client.post(
        "/api/v1/exceptions",
        json={
            "finding_id": "F1",
            "rule_id": "R1",
            "justification": "x",
            "admin_name": "X",
            "admin_email": "not-an-email",
        },
    )
    assert resp.status_code == 422


def test_create_exception_with_invalid_job_id_still_succeeds(client):
    """job_id no formato fingerprint legado não deve quebrar — registra sem vínculo."""
    with patch("app.routers.exceptions.send_exception_notification_email"):
        resp = client.post(
            "/api/v1/exceptions",
            json={
                "job_id": "job_xml_legacy_fingerprint",
                "finding_id": "F1",
                "rule_id": "R1",
                "justification": "x",
                "admin_name": "X",
                "admin_email": "admin@x.com",
            },
        )
    assert resp.status_code == 201
    assert resp.json()["job_id"] is None


def test_list_exceptions_returns_only_tenant_data(client):
    with patch("app.routers.exceptions.send_exception_notification_email"):
        client.post(
            "/api/v1/exceptions",
            json={
                "finding_id": "F1",
                "rule_id": "R1",
                "justification": "x",
                "admin_name": "Admin",
                "admin_email": "a@x.com",
            },
        )
    resp = client.get("/api/v1/exceptions")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    assert rows[0]["status"] == "OPEN"


def test_list_exceptions_filter_by_status_approved_returns_empty(client):
    """Sem nada APPROVED, filtro retorna lista vazia."""
    resp = client.get("/api/v1/exceptions?status=APPROVED")
    assert resp.status_code == 200
    assert resp.json() == []


def test_decide_exception_approves_and_records_decided_by(client, auth_user):
    with patch("app.routers.exceptions.send_exception_notification_email"):
        create_resp = client.post(
            "/api/v1/exceptions",
            json={
                "finding_id": "F1",
                "rule_id": "R1",
                "justification": "x",
                "admin_name": "Admin",
                "admin_email": "a@x.com",
            },
        )
    ex_id = create_resp.json()["id"]

    resp = client.post(
        f"/api/v1/exceptions/{ex_id}/decision",
        json={"status": "APPROVED", "decision_comment": "OK"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "APPROVED"
    assert body["decided_by"] == auth_user.email
    assert body["decision_comment"] == "OK"
    assert body["decided_at"] is not None


def test_decide_exception_rejects_invalid_status(client):
    resp = client.post(
        f"/api/v1/exceptions/{uuid.uuid4()}/decision",
        json={"status": "MAYBE"},
    )
    assert resp.status_code == 422


def test_decide_exception_404_for_nonexistent(client):
    resp = client.post(
        f"/api/v1/exceptions/{uuid.uuid4()}/decision",
        json={"status": "APPROVED"},
    )
    assert resp.status_code == 404


def test_decide_exception_409_when_already_decided(client):
    with patch("app.routers.exceptions.send_exception_notification_email"):
        create_resp = client.post(
            "/api/v1/exceptions",
            json={
                "finding_id": "F1",
                "rule_id": "R1",
                "justification": "x",
                "admin_name": "Admin",
                "admin_email": "a@x.com",
            },
        )
    ex_id = create_resp.json()["id"]
    client.post(
        f"/api/v1/exceptions/{ex_id}/decision",
        json={"status": "APPROVED"},
    )
    # Segunda tentativa deve falhar com 409
    resp = client.post(
        f"/api/v1/exceptions/{ex_id}/decision",
        json={"status": "REJECTED"},
    )
    assert resp.status_code == 409
