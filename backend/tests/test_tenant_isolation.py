"""Suíte sistemática de isolamento cross-tenant (#412).

Auditoria multi-tenant de 02/07/2026 encontrou cobertura só pontual
(test_exceptions.py::test_list_exceptions_returns_only_tenant_data) — nada
impedia regressão silenciosa em jobs/documents/reports/support/exceptions.

Padrão: dois tenants reais no banco (A e B), recurso criado no tenant A,
usuário do tenant B tentando GET/PATCH/POST por id deve receber 404 — nunca
200 com dado de outro tenant, nunca 500 (que vazaria existência do recurso
por comportamento diferenciado). Parametrizado por recurso para crescer
junto com a API, conforme pedido no Definition of Done da issue.

DB real (Postgres do testcontainer/CI) com transaction rollback por teste —
mesmo padrão de tests/test_exceptions.py.
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.documents import Document
from app.models.exception_requests import ExceptionRequest
from app.models.jobs import Job
from app.models.reports import Report
from app.models.support import SupportTicket

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz"
)
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Fixtures compartilhadas ────────────────────────────────────────────────


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _make_tenant_and_user(session, *, label: str) -> User:
    tenant = Tenant(name=f"Empresa {label} Teste", slug=f"tenant-{label}-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"user-{label}-{uuid.uuid4()}@tribultz.com",
        full_name=f"Operador {label}",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="admin",
        account_type="empresa",
        email_verified=True,
    )
    session.add(user)
    session.flush()
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(name="tenant_a_user")
def tenant_a_user_fixture(session) -> User:
    return _make_tenant_and_user(session, label="a")


@pytest.fixture(name="tenant_b_user")
def tenant_b_user_fixture(session) -> User:
    return _make_tenant_and_user(session, label="b")


def _client_as(session, user: User) -> TestClient:
    def override_get_db():
        yield session

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


@pytest.fixture(name="_clear_overrides", autouse=True)
def _clear_overrides_fixture():
    yield
    app.dependency_overrides.clear()


# ── Fábricas de recurso (tenant A) ──────────────────────────────────────────


def _make_job(session, tenant_a_user: User) -> Job:
    job = Job(tenant_id=tenant_a_user.tenant_id, job_type="validate_batch", status="SUCCESS")
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def _make_document(session, tenant_a_user: User) -> Document:
    doc_id = uuid.uuid4()
    # Chave já sob o prefixo "confirmed" + fiscal_metadata.storage_evidence
    # coerente — evita que get_download_url tente re-pinar contra um S3 real
    # (_has_pinned_content precisa dar True; ver app/routers/documents.py).
    storage_key = f"documents/{tenant_a_user.tenant_id}/nfe/confirmed/{doc_id}/deadbeef"
    doc = Document(
        id=doc_id,
        tenant_id=tenant_a_user.tenant_id,
        user_id=tenant_a_user.id,
        doc_type="nfe",
        storage_key=storage_key,
        status="confirmed",
        fiscal_metadata={"storage_evidence": {"storage_key": storage_key}},
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _make_report(session, tenant_a_user: User) -> Report:
    report = Report(
        tenant_id=tenant_a_user.tenant_id,
        user_id=tenant_a_user.id,
        report_type="validation",
        storage_key=f"reports/{tenant_a_user.tenant_id}/validation/{uuid.uuid4()}.pdf",
        file_size=100,
        report_hash="a" * 64,
        status="ready",
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return report


def _make_exception(session, tenant_a_user: User) -> ExceptionRequest:
    row = ExceptionRequest(
        tenant_id=tenant_a_user.tenant_id,
        finding_id="F1",
        rule_id="R1",
        justification="x",
        status="OPEN",
        admin_name="Admin",
        admin_email="a@x.com",
        created_by=str(tenant_a_user.email),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _make_ticket(session, tenant_a_user: User) -> SupportTicket:
    ticket = SupportTicket(
        tenant_id=tenant_a_user.tenant_id,
        user_id=tenant_a_user.id,
        title="Ticket tenant A",
        description="Descrição",
        status="open",
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


# ── jobs ─────────────────────────────────────────────────────────────────


class TestJobIsolation:
    def test_get_job_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        job = _make_job(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get(f"/api/v1/jobs/{job.id}")
        assert resp.status_code == 404

    def test_owner_tenant_can_read_its_own_job(self, session, tenant_a_user, tenant_b_user):
        job = _make_job(session, tenant_a_user)
        client_a = _client_as(session, tenant_a_user)

        resp = client_a.get(f"/api/v1/jobs/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(job.id)

    def test_patch_job_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        job = _make_job(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.patch(f"/api/v1/jobs/{job.id}", json={"status": "FAILED"})
        assert resp.status_code == 404

        # Confirma que o PATCH do tenant B não alterou o job do tenant A.
        session.expire_all()
        untouched = session.get(Job, job.id)
        assert untouched is not None
        assert untouched.status == "SUCCESS"

    def test_list_jobs_from_other_tenant_is_empty(self, session, tenant_a_user, tenant_b_user):
        _make_job(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get("/api/v1/jobs")
        assert resp.status_code == 200
        assert resp.json() == []


# ── documents ────────────────────────────────────────────────────────────


class TestDocumentIsolation:
    def test_download_url_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        doc = _make_document(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get(f"/api/v1/documents/{doc.id}/download")
        assert resp.status_code == 404

    def test_owner_tenant_can_request_download(self, session, tenant_a_user):
        doc = _make_document(session, tenant_a_user)
        client_a = _client_as(session, tenant_a_user)

        with patch("app.routers.documents.s3_tool.get_object_url", return_value="https://s3.example.com/x"):
            resp = client_a.get(f"/api/v1/documents/{doc.id}/download")
        assert resp.status_code == 200

    def test_list_documents_from_other_tenant_is_empty(self, session, tenant_a_user, tenant_b_user):
        _make_document(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get("/api/v1/documents")
        assert resp.status_code == 200
        assert resp.json() == []


# ── reports ──────────────────────────────────────────────────────────────


class TestReportIsolation:
    def test_download_report_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        report = _make_report(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get(f"/api/v1/reports/{report.id}/download")
        assert resp.status_code == 404

    def test_owner_tenant_can_download_its_own_report(self, session, tenant_a_user):
        report = _make_report(session, tenant_a_user)
        client_a = _client_as(session, tenant_a_user)

        with patch("app.routers.reports.s3_tool.get_object_url", return_value="https://s3.example.com/r"):
            resp = client_a.get(f"/api/v1/reports/{report.id}/download")
        assert resp.status_code == 200

    def test_list_reports_from_other_tenant_is_empty(self, session, tenant_a_user, tenant_b_user):
        _make_report(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get("/api/v1/reports")
        assert resp.status_code == 200
        assert resp.json() == []


# ── exceptions ───────────────────────────────────────────────────────────


class TestExceptionIsolation:
    def test_decide_exception_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        row = _make_exception(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.post(
            f"/api/v1/exceptions/{row.id}/decision",
            json={"status": "APPROVED", "decision_comment": "x"},
        )
        assert resp.status_code == 404

        session.expire_all()
        untouched = session.get(ExceptionRequest, row.id)
        assert untouched is not None
        assert untouched.status == "OPEN"

    def test_list_exceptions_from_other_tenant_is_empty(self, session, tenant_a_user, tenant_b_user):
        _make_exception(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get("/api/v1/exceptions")
        assert resp.status_code == 200
        assert resp.json() == []


# ── support tickets ──────────────────────────────────────────────────────


class TestSupportTicketIsolation:
    def test_get_ticket_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        ticket = _make_ticket(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get(f"/api/v1/support/tickets/{ticket.id}")
        assert resp.status_code == 404

    def test_owner_tenant_can_read_its_own_ticket(self, session, tenant_a_user):
        ticket = _make_ticket(session, tenant_a_user)
        client_a = _client_as(session, tenant_a_user)

        resp = client_a.get(f"/api/v1/support/tickets/{ticket.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == str(ticket.id)

    def test_add_message_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        ticket = _make_ticket(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.post(f"/api/v1/support/tickets/{ticket.id}/messages", json={"body": "oi"})
        assert resp.status_code == 404

    def test_list_messages_from_other_tenant_returns_404(self, session, tenant_a_user, tenant_b_user):
        ticket = _make_ticket(session, tenant_a_user)
        client_b = _client_as(session, tenant_b_user)

        resp = client_b.get(f"/api/v1/support/tickets/{ticket.id}/messages")
        assert resp.status_code == 404

    def test_non_staff_cannot_update_ticket_status_of_own_tenant(self, session, tenant_a_user):
        """Regressão de guarda (#411): status só via equipe Tribultz (superadmin),
        mesmo dentro do próprio tenant — não é isolamento cross-tenant, mas a
        mesma suíte é o lugar certo para não perder essa garantia de acesso."""
        ticket = _make_ticket(session, tenant_a_user)
        client_a = _client_as(session, tenant_a_user)

        resp = client_a.patch(f"/api/v1/support/tickets/{ticket.id}/status", json={"status": "resolved"})
        assert resp.status_code == 403


# ── tabela vestigial `messages` (#412, precedente #365/#397) ─────────────


class TestVestigialMessagesTableDropped:
    def test_messages_table_does_not_exist(self, session):
        from sqlalchemy import inspect

        inspector = inspect(session.get_bind())
        assert "messages" not in inspector.get_table_names()

    def test_no_model_references_messages_table(self):
        """Nenhum model ativo declara __tablename__ == "messages" —
        support_messages é tabela homônima, não relacionada (#412)."""
        from app.database import Base

        tablenames = set(Base.metadata.tables.keys())
        assert "messages" not in tablenames
        assert "support_messages" in tablenames  # continua ativa, não confundir
