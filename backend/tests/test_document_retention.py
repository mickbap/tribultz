"""Job de retenção de documentos — 12 meses (Escopo 4.3, go-live de billing).

Documento com mais de 12 meses deve ser apagado do S3 e do banco; documento
mais recente não é tocado. Falha ao apagar do S3 mantém a linha no banco
(retry no próximo ciclo, não perde o registro silenciosamente).
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant, User
from app.models.documents import Document
from app.core.security import get_password_hash

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tribultz:tribultz@localhost:5432/tribultz",
)
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def db_session():
    conn = engine.connect()
    tx = conn.begin()
    session = TestingSessionLocal(bind=conn)
    yield session
    session.close()
    tx.rollback()
    conn.close()


def _make_document(session, *, created_at, storage_key=None):
    tenant = Tenant(name="Empresa Retenção Teste", slug=f"retention-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"retention-{uuid.uuid4()}@test.com",
        full_name="Usuário Retenção",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="admin",
        account_type="empresa",
        email_verified=True,
    )
    session.add(user)
    session.flush()

    doc = Document(
        tenant_id=tenant.id,
        user_id=user.id,
        doc_type="nfe",
        storage_key=storage_key or f"docs/{uuid.uuid4()}.xml",
        status="confirmed",
    )
    session.add(doc)
    session.flush()
    session.execute(
        update(Document).where(Document.id == doc.id).values(created_at=created_at)
    )
    session.commit()
    session.refresh(doc)
    return doc


class TestPurgeExpiredDocuments:
    def test_document_older_than_12_months_is_deleted(self, db_session, monkeypatch):
        from app.tasks import task_j_retention

        monkeypatch.setattr(task_j_retention, "SessionLocal", lambda: db_session)
        # rollback/close do fixture cuidam da limpeza — task não deve fechar a sessão de teste
        db_session.close = lambda: None

        old_doc = _make_document(
            db_session, created_at=datetime.now(timezone.utc) - timedelta(days=400)
        )

        with patch(
            "app.tasks.task_j_retention.delete_object"
        ) as mock_delete:
            task_j_retention.purge_expired_documents()

        mock_delete.assert_called_once_with(old_doc.storage_key)
        db_session.expire_all()
        assert db_session.get(Document, old_doc.id) is None

    def test_document_within_12_months_is_kept(self, db_session, monkeypatch):
        from app.tasks import task_j_retention

        monkeypatch.setattr(task_j_retention, "SessionLocal", lambda: db_session)
        db_session.close = lambda: None

        recent_doc = _make_document(
            db_session, created_at=datetime.now(timezone.utc) - timedelta(days=30)
        )

        with patch("app.tasks.task_j_retention.delete_object") as mock_delete:
            task_j_retention.purge_expired_documents()

        mock_delete.assert_not_called()
        db_session.expire_all()
        assert db_session.get(Document, recent_doc.id) is not None

    def test_s3_delete_failure_keeps_document_for_retry(self, db_session, monkeypatch):
        from app.tasks import task_j_retention

        monkeypatch.setattr(task_j_retention, "SessionLocal", lambda: db_session)
        db_session.close = lambda: None

        old_doc = _make_document(
            db_session, created_at=datetime.now(timezone.utc) - timedelta(days=400)
        )

        with patch(
            "app.tasks.task_j_retention.delete_object",
            side_effect=Exception("S3 indisponível"),
        ):
            task_j_retention.purge_expired_documents()

        db_session.expire_all()
        # Não apagou do banco — mantém para nova tentativa no próximo ciclo
        assert db_session.get(Document, old_doc.id) is not None
