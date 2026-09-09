"""Tests for the Documents endpoints (Issues #122, #124, #125, #126).

All S3 calls are patched so the suite runs without live MinIO.
All DB calls use a fully mocked Session via dependency_overrides.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.documents import Document
from app.routers.documents import (
    MAX_DOCUMENT_BYTES,
    StoredObjectEvidence,
    StoredObjectInvalid,
    StoredObjectMissing,
    StoredObjectTooLarge,
    StoredObjectUnavailable,
    _load_authoritative_object,
)

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


def _stored_evidence(
    content: bytes = b"<NFe><chNFe>ABC123</chNFe></NFe>",
    *,
    content_type: str = "application/xml",
) -> StoredObjectEvidence:
    return StoredObjectEvidence(
        content=content,
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        content_type=content_type,
        etag=hashlib.sha256(b"etag:" + content).hexdigest()[:32],
    )


def _storage_snapshot(evidence: StoredObjectEvidence) -> dict[str, Any]:
    return {
        "checksum_sha256": evidence.checksum_sha256,
        "size_bytes": evidence.size_bytes,
        "content_type": evidence.content_type,
        "etag": evidence.etag,
    }


@pytest.fixture(autouse=True)
def stored_copy():
    with patch("app.routers.documents.s3_tool.put_object") as upload:
        yield upload


def _pinned_snapshot(evidence):
    return {**_storage_snapshot(evidence), "storage_key": (
        f"documents/{TENANT_ID}/nfe/confirmed/{DOC_ID}/{evidence.checksum_sha256}"
    )}


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
            json={"doc_type": "invalid_type"},
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
        authoritative = _stored_evidence()

        with (
            patch("app.routers.documents._load_authoritative_object", return_value=authoritative),
            patch("app.routers.documents._extract_xml_metadata", return_value={"chave_acesso": "ABC123"}),
        ):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"document_id": str(DOC_ID), "file_size": 4096},
            )

        assert resp.status_code == 200
        assert doc.status == "confirmed"  # type: ignore[truthy-function]
        assert doc.file_size == authoritative.size_bytes  # type: ignore[truthy-function]
        assert doc.file_size != 4096  # type: ignore[comparison-overlap]  # client is not authoritative
        assert doc.uploaded_at is not None

    def test_confirm_already_confirmed_is_idempotent(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        authoritative = _stored_evidence()
        doc.file_size = authoritative.size_bytes  # type: ignore[assignment]
        doc.fiscal_metadata = {  # type: ignore[assignment]
            "storage_evidence": _pinned_snapshot(authoritative)
        }
        doc.storage_key = _pinned_snapshot(authoritative)["storage_key"]
        self._setup_db(mock_db, doc)

        with patch("app.routers.documents._load_authoritative_object", return_value=authoritative):
            resp = client_with_auth.post(
                self.ENDPOINT,
                json={"document_id": str(DOC_ID)},
            )

        assert resp.status_code == 200
        mock_db.commit.assert_not_called()

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
        authoritative = _stored_evidence()

        extracted = {"chave_acesso": "35250101234567890001550010000001231234567890", "cnpj_emitente": "01234567000190"}

        with (
            patch("app.routers.documents._load_authoritative_object", return_value=authoritative),
            patch("app.routers.documents._extract_xml_metadata", return_value=extracted),
        ):
            client_with_auth.post(
                self.ENDPOINT,
                json={"document_id": str(DOC_ID)},
            )

        assert doc.fiscal_metadata["chave_acesso"] == extracted["chave_acesso"]  # type: ignore[index]
        assert doc.fiscal_metadata["cnpj_emitente"] == extracted["cnpj_emitente"]  # type: ignore[index]
        assert doc.fiscal_metadata["storage_evidence"] == _pinned_snapshot(authoritative)  # type: ignore[index]

    def test_missing_object_is_rejected(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)

        with patch("app.routers.documents._load_authoritative_object", side_effect=StoredObjectMissing):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 409
        assert doc.status == "pending_upload"  # type: ignore[truthy-function]
        mock_db.commit.assert_not_called()

    def test_s3_failure_is_fail_closed(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)

        with patch(
            "app.routers.documents._load_authoritative_object",
            side_effect=StoredObjectUnavailable,
        ):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 503
        assert doc.status == "pending_upload"  # type: ignore[truthy-function]
        mock_db.commit.assert_not_called()

    def test_invalid_xml_keeps_existing_best_effort_policy(self, client_with_auth, mock_db):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)
        authoritative = _stored_evidence(b"not xml")

        with patch("app.routers.documents._load_authoritative_object", return_value=authoritative):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 200
        assert doc.status == "confirmed"  # type: ignore[truthy-function]
        assert set(doc.fiscal_metadata) == {"storage_evidence", "upload_storage_key"}  # type: ignore[arg-type]

    def test_optional_extraction_failure_cannot_mask_required_validation(
        self, client_with_auth, mock_db
    ):
        doc = _make_doc(status="pending_upload")
        self._setup_db(mock_db, doc)
        authoritative = _stored_evidence()

        with (
            patch("app.routers.documents._load_authoritative_object", return_value=authoritative),
            patch("app.routers.documents._extract_xml_metadata", side_effect=RuntimeError("optional")),
        ):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 200
        assert doc.fiscal_metadata["storage_evidence"] == _pinned_snapshot(authoritative)  # type: ignore[index]

    def test_overwrite_after_confirm_is_rejected(self, client_with_auth, mock_db):
        original = _stored_evidence(b"original")
        overwritten = _stored_evidence(b"changed!")
        doc = _make_doc(status="confirmed")
        doc.file_size = original.size_bytes  # type: ignore[assignment]
        doc.fiscal_metadata = {  # type: ignore[assignment]
            "storage_evidence": _storage_snapshot(original)
        }
        self._setup_db(mock_db, doc)

        with patch("app.routers.documents._load_authoritative_object", return_value=overwritten):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 409
        assert "sobrescrito" in resp.json()["detail"]
        mock_db.commit.assert_not_called()

    def test_tenant_predicate_is_applied_to_confirmation(self, client_with_auth, mock_db):
        scalar_result = MagicMock()
        scalar_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = scalar_result

        resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 404
        statement = mock_db.execute.call_args.args[0]
        sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
        assert TENANT_ID.hex in sql
        assert "FOR UPDATE" in sql

    def test_legacy_confirmed_row_gets_authoritative_snapshot(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        doc.fiscal_metadata = {"legacy": True}  # type: ignore[assignment]
        self._setup_db(mock_db, doc)
        authoritative = _stored_evidence()

        with patch("app.routers.documents._load_authoritative_object", return_value=authoritative):
            resp = client_with_auth.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})

        assert resp.status_code == 200
        assert doc.fiscal_metadata["legacy"] is True  # type: ignore[index]
        assert doc.fiscal_metadata["storage_evidence"] == _pinned_snapshot(authoritative)  # type: ignore[index]
        mock_db.commit.assert_called_once()

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.post(self.ENDPOINT, json={"document_id": str(DOC_ID)})
        assert resp.status_code == 401


class TestAuthoritativeS3Read:
    class _BoundedStream:
        def __init__(self, total_bytes: int):
            self.remaining = total_bytes
            self.total_returned = 0
            self.max_requested = 0
            self.closed = False

        def read(self, requested: int) -> bytes:
            self.max_requested = max(self.max_requested, requested)
            if self.remaining == 0:
                return b""
            returned = min(requested, self.remaining)
            self.remaining -= returned
            self.total_returned += returned
            return b"x" * returned

        def close(self) -> None:
            self.closed = True

    def test_oversize_stream_aborts_at_limit_without_large_fixture(self):
        stream = self._BoundedStream(MAX_DOCUMENT_BYTES + 1)
        client = MagicMock()
        client.get_object.return_value = {
            # Simula metadata inconsistente/defasada para provar o teto durante a leitura.
            "ContentLength": MAX_DOCUMENT_BYTES,
            "ContentType": "application/xml",
            "Body": stream,
            "ETag": '"etag"',
        }

        with (
            patch("app.routers.documents.s3_tool._client", return_value=client),
            pytest.raises(StoredObjectTooLarge),
        ):
            _load_authoritative_object(STORAGE_KEY, "application/xml")

        assert stream.total_returned == MAX_DOCUMENT_BYTES + 1
        assert stream.max_requested <= 64 * 1024
        assert stream.closed is True

    def test_authoritative_oversize_is_rejected_before_body_read(self):
        stream = self._BoundedStream(1)
        client = MagicMock()
        client.get_object.return_value = {
            "ContentLength": MAX_DOCUMENT_BYTES + 1,
            "ContentType": "application/xml",
            "Body": stream,
        }

        with (
            patch("app.routers.documents.s3_tool._client", return_value=client),
            pytest.raises(StoredObjectTooLarge),
        ):
            _load_authoritative_object(STORAGE_KEY, "application/xml")

        assert stream.total_returned == 0
        assert stream.closed is True

    def test_authoritative_content_type_mismatch_is_rejected(self):
        stream = self._BoundedStream(1)
        client = MagicMock()
        client.get_object.return_value = {
            "ContentLength": 1,
            "ContentType": "application/pdf",
            "Body": stream,
        }

        with (
            patch("app.routers.documents.s3_tool._client", return_value=client),
            pytest.raises(StoredObjectInvalid),
        ):
            _load_authoritative_object(STORAGE_KEY, "application/xml")

        assert stream.total_returned == 0
        assert stream.closed is True

    def test_missing_s3_object_is_classified(self):
        client = MagicMock()
        client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "missing"}},
            "GetObject",
        )

        with (
            patch("app.routers.documents.s3_tool._client", return_value=client),
            pytest.raises(StoredObjectMissing),
        ):
            _load_authoritative_object(STORAGE_KEY, "application/xml")

    def test_s3_transport_failure_is_classified(self):
        client = MagicMock()
        client.get_object.side_effect = ConnectionError("S3 unavailable")

        with (
            patch("app.routers.documents.s3_tool._client", return_value=client),
            pytest.raises(StoredObjectUnavailable),
        ):
            _load_authoritative_object(STORAGE_KEY, "application/xml")

    def test_authoritative_size_and_checksum_come_from_s3(self):
        content = b"<NFe/>"
        stream = self._BoundedStream(len(content))
        client = MagicMock()
        client.get_object.return_value = {
            "ContentLength": len(content),
            "ContentType": "application/xml",
            "Body": stream,
            "ETag": '"etag"',
        }

        with patch("app.routers.documents.s3_tool._client", return_value=client):
            evidence = _load_authoritative_object(STORAGE_KEY, "application/xml")

        # The lazy stream intentionally yields x bytes: evidence reflects stored bytes,
        # never a client declaration or the local `content` variable.
        assert evidence.size_bytes == len(content)
        assert evidence.checksum_sha256 == hashlib.sha256(b"x" * len(content)).hexdigest()
        assert stream.closed is True


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
    @pytest.fixture(autouse=True)
    def legacy_object(self):
        with patch("app.routers.documents._load_authoritative_object", return_value=_stored_evidence()) as read:
            yield read

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


class TestConfirmedContentIntegrity:
    def test_replayed_put_cannot_change_confirmed_download(self, client_with_auth, mock_db, stored_copy):
        doc = _make_doc()
        objects = {STORAGE_KEY: b"<NFe>original</NFe>"}
        mock_db.execute.return_value.scalar_one_or_none.return_value = doc

        def read(key, content_type):
            return _stored_evidence(objects[key])

        def put(*, key, data, content_type):
            # Simulate overwrite exactly between the authoritative read and final write.
            objects[STORAGE_KEY] = b"<NFe>attacker</NFe>"
            objects[key] = data

        stored_copy.side_effect = put
        with (
            patch("app.routers.documents._load_authoritative_object", side_effect=read),
            patch("app.routers.documents.s3_tool.get_object_url", side_effect=lambda key, **kw: key),
        ):
            response = client_with_auth.post("/api/v1/documents/confirm", json={"document_id": str(DOC_ID)})
            assert response.status_code == 200
            response = client_with_auth.get(f"/api/v1/documents/{DOC_ID}/download")
            assert response.status_code == 200
            key = response.json()["download_url"]
            assert key != STORAGE_KEY
            assert objects[key] == b"<NFe>original</NFe>"
            assert objects[STORAGE_KEY] == b"<NFe>attacker</NFe>"
            assert cast(dict, doc.fiscal_metadata)["upload_storage_key"] == STORAGE_KEY

    def test_final_write_failure_does_not_confirm(self, client_with_auth, mock_db, stored_copy):
        doc = _make_doc()
        mock_db.execute.return_value.scalar_one_or_none.return_value = doc
        stored_copy.side_effect = ConnectionError("storage unavailable")
        with patch("app.routers.documents._load_authoritative_object", return_value=_stored_evidence()):
            response = client_with_auth.post("/api/v1/documents/confirm", json={"document_id": str(DOC_ID)})
        assert response.status_code == 503
        assert cast(str, doc.status) == "pending_upload"
        assert cast(str, doc.storage_key) == STORAGE_KEY
        mock_db.commit.assert_not_called()

    def test_changed_legacy_object_cannot_be_downloaded(self, client_with_auth, mock_db, stored_copy):
        doc = _make_doc(status="confirmed")
        doc.fiscal_metadata = {"storage_evidence": _storage_snapshot(_stored_evidence(b"original"))}  # type: ignore[assignment]
        mock_db.execute.return_value.scalar_one_or_none.return_value = doc
        with (
            patch("app.routers.documents._load_authoritative_object", return_value=_stored_evidence(b"changed")),
            patch("app.routers.documents.s3_tool.get_object_url") as sign,
        ):
            response = client_with_auth.get(f"/api/v1/documents/{DOC_ID}/download")
        assert response.status_code == 409
        sign.assert_not_called()
        stored_copy.assert_not_called()

    def test_pinned_download_never_reads_staging(self, client_with_auth, mock_db):
        doc = _make_doc(status="confirmed")
        snapshot = _pinned_snapshot(_stored_evidence())
        doc.storage_key = snapshot["storage_key"]
        doc.fiscal_metadata = {"storage_evidence": snapshot, "upload_storage_key": STORAGE_KEY}  # type: ignore[assignment]
        mock_db.execute.return_value.scalar_one_or_none.return_value = doc
        with (
            patch("app.routers.documents._load_authoritative_object") as read,
            patch("app.routers.documents.s3_tool.get_object_url", return_value="https://s3/final") as sign,
        ):
            response = client_with_auth.get(f"/api/v1/documents/{DOC_ID}/download")
        assert response.status_code == 200
        read.assert_not_called()
        assert sign.call_args.kwargs["key"] == snapshot["storage_key"]
