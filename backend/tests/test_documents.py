"""Tests for the Documents endpoints (Issues #122, #124, #125, #126).

All S3 calls are patched so the suite runs without live MinIO.
All DB calls use a fully mocked Session via dependency_overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.documents import Document

# ── Fixtures ───────────────────────────────────────────────────────────────────

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()
STORAGE_KEY = f"documents/{TENANT_ID}/nfe/{uuid.uuid4()}.xml"

_mock_user = User(
    id=USER_ID,
    email="techlead@tribultz.com",
    tenant_id=TENANT_ID,
    full_name="Tech Lead",
    is_active=True,
    role="admin",
    password_hash="x",
)


def _override_current_user():
    return _mock_user


def _make_doc(
    status: str = "pending_upload",
    doc_type: str = "nfe",
    doc_id: uuid.UUID | None = None,
) -> Document:
    doc = Document(
        id=doc_id or DOC_ID,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        doc_type=doc_type,
        original_filename="nota.xml",
        storage_key=STORAGE_KEY,
        content_type="application/xml",
        status=status,
        file_size=None,
        expires_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        fiscal_metadata={},
    )
    return doc


@pytest.fixture()
def client_with_auth():
    """TestClient with current_user overridden."""
    app.dependency_overrides[get_current_user] = _override_current_user
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def mock_db():
    """Yield a MagicMock Session injected via dependency override."""
    session = MagicMock()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


# ── Issue #122: POST /upload-url ───────────────────────────────────────────────

class TestUploadUrl:
    ENDPOINT = "/api/v1/documents/upload-url"

    def test_returns_201_and_presigned_url(self, client_with_auth, mock_db):
        mock_db.add = MagicMock()
        mock_db.commit = MagicMock()
        mock_db.refresh = lambda doc: setattr(doc, "id", DOC_ID)

        with patch(
            "app.routers.documents._generate_presigned_put",
            return_value="https://minio.local/bucket/key?X-Amz-Signature=abc",
        ):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"doc_type": "nfe", "original_filename": "nota.xml", "content_type": "application/xml"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert "upload_url" in data
        assert data["upload_url"].startswith("https://")
        assert "document_id" in data
        assert "storage_key" in data
        assert "expires_at" in data

    def test_storage_key_contains_tenant_and_doctype(self, client_with_auth, mock_db):
        mock_db.refresh = lambda doc: setattr(doc, "id", DOC_ID)

        with patch(
            "app.routers.documents._generate_presigned_put",
            return_value="https://minio.local/x",
        ):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"doc_type": "cte"},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert str(TENANT_ID) in data["storage_key"]
        assert "cte" in data["storage_key"]

    def test_invalid_doc_type_returns_422(self, client_with_auth):
        resp = client_with_auth.post(
            self.ENDPOINT,
            json={"doc_type": "boleto"},
        )
        assert resp.status_code == 422

    def test_invalid_content_type_returns_422(self, client_with_auth):
        resp = client_with_auth.post(
            self.ENDPOINT,
            json={"doc_type": "nfe", "content_type": "text/html"},
        )
        assert resp.status_code == 422

    def test_s3_error_returns_503(self, client_with_auth, mock_db):
        mock_db.refresh = lambda doc: setattr(doc, "id", DOC_ID)

        with patch(
            "app.routers.documents._generate_presigned_put",
            side_effect=Exception("S3 unreachable"),
        ):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"doc_type": "nfe"},
            )

        assert resp.status_code == 503

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.post(self.ENDPOINT, json={"doc_type": "nfe"})
        assert resp.status_code == 401


# ── Issue #124: POST /confirm ──────────────────────────────────────────────────

class TestConfirmUpload:
    ENDPOINT = "/api/v1/documents/confirm"

    def _setup_db(self, mock_db: MagicMock, doc: Document):
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = doc
        mock_db.execute.return_value = scalar_result
        mock_db.commit = MagicMock()
        mock_db.refresh = MagicMock()

    def test_confirm_pending_document(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)

        with patch("app.routers.documents._extract_xml_metadata", return_value={"chave_acesso": "ABC123"}):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"document_id": str(DOC_ID), "file_size": 4096},
            )

        assert resp.status_code == 200
        assert doc.status == "confirmed"  # type: ignore[truthy-function]
        assert doc.file_size == 4096  # type: ignore[truthy-function]
        assert doc.uploaded_at is not None

    def test_confirm_already_confirmed_is_idempotent(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        self._setup_db(mock_db, doc)

        resp = client_with_auth.post(
            self.ENDPOINT,
            json={"document_id": str(DOC_ID)},
        )

        assert resp.status_code == 200

    def test_confirm_error_status_returns_409(self, client_with_auth, mock_db):
        doc = _make_doc(status="error")
        self._setup_db(mock_db, doc)

        resp = client_with_auth.post(
            self.ENDPOINT,
            json={"document_id": str(DOC_ID)},
        )

        assert resp.status_code == 409

    def test_confirm_nonexistent_returns_404(self, client_with_auth, mock_db):
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = scalar_result

        resp = client_with_auth.post(
            self.ENDPOINT,
            json={"document_id": str(uuid.uuid4())},
        )

        assert resp.status_code == 404

    def test_xml_metadata_extracted_on_confirm(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)

        extracted = {"chave_acesso": "35250101234567890001550010000001231234567890", "cnpj_emitente": "01234567000190"}

        with patch("app.routers.documents._extract_xml_metadata", return_value=extracted):
            client_with_auth.post(
                self.ENDPOINT,
                json={"document_id": str(DOC_ID)},
            )

        assert doc.fiscal_metadata == extracted  # type: ignore[truthy-function]

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})
        assert resp.status_code == 401


# ── Issue #125: GET /documents ─────────────────────────────────────────────────

class TestListDocuments:
    ENDPOINT = "/api/v1/documents"

    def _setup_db_list(self, mock_db: MagicMock, docs: list[Document]):
        scalars_result = MagicMock()
        scalars_result.all.return_value = docs
        execute_result = MagicMock()
        execute_result.scalars.return_value = scalars_result
        mock_db.scalars.return_value = iter(docs)
        # Also handle db.scalars(stmt).all() pattern via execute path
        mock_db.execute.return_value = execute_result

    def test_returns_list(self, client_with_auth, mock_db):
        docs = [_make_doc(status="confirmed"), _make_doc(status="pending_upload", doc_id=uuid.uuid4())]
        scalar_mock = MagicMock()
        scalar_mock.all.return_value = docs
        mock_db.scalars.return_value = scalar_mock

        resp = client_with_auth.get(self.ENDPOINT)

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_filter_by_doc_type(self, client_with_auth, mock_db):
        scalar_mock = MagicMock()
        scalar_mock.all.return_value = []
        mock_db.scalars.return_value = scalar_mock

        resp = client_with_auth.get(self.ENDPOINT, params={"doc_type": "nfe"})
        assert resp.status_code == 200

    def test_invalid_doc_type_returns_422(self, client_with_auth, mock_db):
        resp = client_with_auth.get(self.ENDPOINT, params={"doc_type": "unknown"})
        assert resp.status_code == 422

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.get(self.ENDPOINT)
        assert resp.status_code == 401


# ── Issue #125: GET /documents/{id}/download ───────────────────────────────────

class TestDownloadUrl:
    def _endpoint(self, doc_id: Any = None) -> str:
        return f"/api/v1/documents/{doc_id or DOC_ID}/download"

    def _setup_db(self, mock_db: MagicMock, doc: Document | None):
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = doc
        mock_db.execute.return_value = scalar_result

    def test_returns_presigned_get_url(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        self._setup_db(mock_db, doc)

        with patch(
            "app.routers.documents.s3_tool.get_object_url",
            return_value="https://minio.local/bucket/key?X-Amz-Signature=xyz",
        ):
            resp = client_with_auth.get(self._endpoint())

        assert resp.status_code == 200
        data = resp.json()
        assert "download_url" in data
        assert data["download_url"].startswith("https://")
        assert "expires_at" in data

    def test_pending_upload_returns_409(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)

        resp = client_with_auth.get(self._endpoint())
        assert resp.status_code == 409

    def test_nonexistent_returns_404(self, client_with_auth, mock_db):
        self._setup_db(mock_db, None)

        resp = client_with_auth.get(self._endpoint(uuid.uuid4()))
        assert resp.status_code == 404

    def test_s3_error_returns_503(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        self._setup_db(mock_db, doc)

        with patch(
            "app.routers.documents.s3_tool.get_object_url",
            side_effect=Exception("MinIO down"),
        ):
            resp = client_with_auth.get(self._endpoint())

        assert resp.status_code == 503

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.get(self._endpoint())
        assert resp.status_code == 401

    def test_uploaded_status_also_allows_download(self, client_with_auth, mock_db):
        doc = _make_doc(status="uploaded")
        self._setup_db(mock_db, doc)

        with patch(
            "app.routers.documents.s3_tool.get_object_url",
            return_value="https://minio.local/x",
        ):
            resp = client_with_auth.get(self._endpoint())

        assert resp.status_code == 200


# ── Document Model Sanity ──────────────────────────────────────────────────────

class TestDocumentModel:
    """Smoke-test the SQLAlchemy model attributes (no DB connection needed)."""

    def test_model_tablename(self):
        assert Document.__tablename__ == "documents"

    def test_model_has_required_columns(self):
        cols = {c.key for c in Document.__table__.columns}
        required = {
            "id", "tenant_id", "user_id", "doc_type", "storage_key",
            "status", "created_at", "updated_at", "fiscal_metadata",
        }
        assert required.issubset(cols)

    def test_model_has_fiscal_metadata_jsonb(self):
        from sqlalchemy.dialects.postgresql import JSONB
        col = Document.__table__.columns["fiscal_metadata"]
        assert isinstance(col.type, JSONB)
