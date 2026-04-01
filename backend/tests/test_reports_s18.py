"""Tests for S18 — Relatório PDF Auditável CBS/IBS (Issues #143–#147).

All S3 calls are patched so the suite runs without live MinIO.
All DB calls use a fully mocked Session via dependency_overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.reports import Report

# ── Fixtures ──────────────────────────────────────────────────────────────────

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()
REPORT_ID = uuid.uuid4()

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


def _make_report(status: str = "ready", report_type: str = "validation") -> Report:
    return Report(
        id=REPORT_ID,
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        job_id=str(uuid.uuid4()),
        report_type=report_type,
        storage_key=f"reports/{TENANT_ID}/validation/{uuid.uuid4()}.pdf",
        file_size=12345,
        report_hash="a" * 64,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _mock_plan():
    """Mock Plan object with slug='profissional' to satisfy plan gate."""
    plan = MagicMock()
    plan.slug = "profissional"
    plan.max_validations = None
    plan.max_ai_messages = None
    return plan


@pytest.fixture()
def client_auth():
    app.dependency_overrides[get_current_user] = _override_current_user
    with patch("app.api.plan_gate._get_active_subscription", return_value=(MagicMock(), _mock_plan())):
        yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def mock_db():
    session = MagicMock()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.pop(get_db, None)


_VALIDATION_BODY = {
    "company_name": "Acme Ltda",
    "cnpj": "12345678000195",
    "reference_period": "2026-03",
    "job_id": str(uuid.uuid4()),
    "findings": [],
    "overall_status": "CONFORME",
    "total_base": "10000",
    "total_cbs": "10",
    "total_ibs": "90",
    "cbs_rate": "0.10",
    "ibs_rate": "0.90",
}

_BATCH_BODY = {
    "company_name": "Acme Ltda",
    "cnpj": "12345678000195",
    "reference_period": "2026-03",
    "job_id": str(uuid.uuid4()),
    "invoices": [
        {"nf_number": "001", "cnpj_emitente": "12345678000195", "valor_total": "500", "status": "PASS"},
    ],
    "overall_status": "CONFORME",
}


# ── TestReportsPost ────────────────────────────────────────────────────────────


class TestReportsPost:
    """POST /api/v1/reports/pdf/validation and /pdf/batch"""

    def test_validation_happy_path(self, client_auth, mock_db):
        mock_db.refresh = lambda r: setattr(r, "id", REPORT_ID)

        with (
            patch("app.routers.reports.generate_validation_report_pdf") as mock_gen,
            patch("app.routers.reports.s3_tool.get_object_url", return_value="https://s3.example.com/key?sig=abc"),
        ):
            mock_gen.return_value = {
                "bytes": b"%PDF-1.4 fake",
                "storage_key": f"reports/{TENANT_ID}/validation/x.pdf",
                "file_size": 13,
            }
            resp = client_auth.post("/api/v1/reports/pdf/validation", json=_VALIDATION_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert "report_id" in data
        assert data["download_url"].startswith("https://")
        assert "expires_at" in data
        assert data["report_hash"]
        assert data["file_size"] == 13

    def test_batch_happy_path(self, client_auth, mock_db):
        mock_db.refresh = lambda r: setattr(r, "id", REPORT_ID)

        with (
            patch("app.routers.reports.generate_batch_report_pdf") as mock_gen,
            patch("app.routers.reports.s3_tool.get_object_url", return_value="https://s3.example.com/batch?sig=xyz"),
        ):
            mock_gen.return_value = {
                "bytes": b"%PDF-1.4 batch",
                "storage_key": f"reports/{TENANT_ID}/batch/y.pdf",
                "file_size": 14,
            }
            resp = client_auth.post("/api/v1/reports/pdf/batch", json=_BATCH_BODY)

        assert resp.status_code == 200
        data = resp.json()
        assert data["file_size"] == 14
        assert data["download_url"].startswith("https://")

    def test_s3_error_returns_503(self, client_auth, mock_db):
        mock_db.refresh = lambda r: setattr(r, "id", REPORT_ID)

        with (
            patch("app.routers.reports.generate_validation_report_pdf") as mock_gen,
            patch("app.routers.reports.s3_tool.get_object_url", side_effect=Exception("MinIO down")),
        ):
            mock_gen.return_value = {
                "bytes": b"%PDF",
                "storage_key": "reports/x/v/z.pdf",
                "file_size": 4,
            }
            resp = client_auth.post("/api/v1/reports/pdf/validation", json=_VALIDATION_BODY)

        assert resp.status_code == 503

    def test_stream_true_returns_streaming_response(self, client_auth, mock_db):
        with patch("app.routers.reports.generate_validation_report_pdf") as mock_gen:
            mock_gen.return_value = {
                "bytes": b"%PDF-1.4 stream",
                "storage_key": "",
                "file_size": 15,
            }
            resp = client_auth.post(
                "/api/v1/reports/pdf/validation?stream=true",
                json=_VALIDATION_BODY,
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        # Should NOT have called db.add when streaming
        mock_db.add.assert_not_called()

    def test_plan_gate_401_without_auth(self):
        c = TestClient(app)
        resp = c.post("/api/v1/reports/pdf/validation", json=_VALIDATION_BODY)
        assert resp.status_code == 401


# ── TestReportsList ────────────────────────────────────────────────────────────


class TestReportsList:
    ENDPOINT = "/api/v1/reports"

    def test_returns_list(self, client_auth, mock_db):
        reports = [_make_report(), _make_report(report_type="batch")]
        scalar_mock = MagicMock()
        scalar_mock.all.return_value = reports
        mock_db.scalars.return_value = scalar_mock

        resp = client_auth.get(self.ENDPOINT)

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 2

    def test_filter_by_report_type(self, client_auth, mock_db):
        scalar_mock = MagicMock()
        scalar_mock.all.return_value = []
        mock_db.scalars.return_value = scalar_mock

        resp = client_auth.get(self.ENDPOINT, params={"report_type": "validation"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unauthenticated_returns_401(self):
        c = TestClient(app)
        resp = c.get(self.ENDPOINT)
        assert resp.status_code == 401


# ── TestReportsDownload ────────────────────────────────────────────────────────


class TestReportsDownload:
    def _endpoint(self, report_id=None):
        return f"/api/v1/reports/{report_id or REPORT_ID}/download"

    def _setup_db(self, mock_db, report):
        scalar_mock = MagicMock()
        scalar_mock.first.return_value = report
        mock_db.scalars.return_value = scalar_mock

    def test_200_with_presigned_url(self, client_auth, mock_db):
        self._setup_db(mock_db, _make_report(status="ready"))

        with patch(
            "app.routers.reports.s3_tool.get_object_url",
            return_value="https://s3.example.com/report.pdf?sig=123",
        ):
            resp = client_auth.get(self._endpoint())

        assert resp.status_code == 200
        data = resp.json()
        assert data["download_url"].startswith("https://")
        assert "expires_at" in data

    def test_404_not_found(self, client_auth, mock_db):
        self._setup_db(mock_db, None)

        resp = client_auth.get(self._endpoint(uuid.uuid4()))
        assert resp.status_code == 404

    def test_409_status_not_ready(self, client_auth, mock_db):
        self._setup_db(mock_db, _make_report(status="generating"))

        resp = client_auth.get(self._endpoint())
        assert resp.status_code == 409

    def test_503_s3_error(self, client_auth, mock_db):
        self._setup_db(mock_db, _make_report(status="ready"))

        with patch(
            "app.routers.reports.s3_tool.get_object_url",
            side_effect=Exception("S3 unreachable"),
        ):
            resp = client_auth.get(self._endpoint())

        assert resp.status_code == 503

    def test_401_without_auth(self):
        c = TestClient(app)
        resp = c.get(self._endpoint())
        assert resp.status_code == 401


# ── TestReportModel ────────────────────────────────────────────────────────────


class TestReportModel:
    """Smoke-test the SQLAlchemy model (no DB connection needed)."""

    def test_model_tablename(self):
        assert Report.__tablename__ == "reports"

    def test_model_has_required_columns(self):
        cols = {c.key for c in Report.__table__.columns}
        required = {
            "id", "tenant_id", "user_id", "job_id", "report_type",
            "storage_key", "file_size", "report_hash", "status",
            "created_at", "updated_at",
        }
        assert required.issubset(cols)

    def test_model_has_check_constraints(self):
        constraint_names = {c.name for c in Report.__table__.constraints}
        assert "reports_report_type_check" in constraint_names
        assert "reports_status_check" in constraint_names

    def test_storage_key_is_unique(self):
        unique_constraints = [
            c for c in Report.__table__.constraints
            if hasattr(c, "columns") and "storage_key" in [col.key for col in c.columns]
            and c.__class__.__name__ == "UniqueConstraint"
        ]
        assert len(unique_constraints) >= 1
