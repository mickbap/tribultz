"""Tests for /api/v1/credits endpoints (#258 Phase 1).

Mocks DB Session and plan-gate (profissional) via dependency_overrides.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.auth import User

TENANT_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

_mock_user = User(
    id=USER_ID,
    email="techlead@tribultz.com",
    tenant_id=TENANT_ID,
    full_name="Tech Lead",
    is_active=True,
    role="admin",
    password_hash="x",
)


def _override_user():
    return _mock_user


def _bypass_plan_gate(*_args, **_kwargs):
    """Replace require_plan(...) factory so the inner dependency just returns the user."""
    def _ok():
        return _mock_user
    return _ok


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = _override_user
    # require_plan is a factory — patch by replacing the dependency it returns.
    # Easiest: override every plan_gate dependency by inserting a passthrough for the
    # specific Depends object. We accomplish this by overriding the factory output via
    # FastAPI's dependency_overrides keyed on the inner callable.
    # Since router builds Depends(require_plan(...)) at import time, the inner callable
    # already exists — patch via app.dependency_overrides on the inner closure is awkward,
    # so we monkeypatch the helper inside the call chain by overriding get_db plus a
    # local DB-driven Subscription. For the simple aggregation tests below it's enough
    # to mock the DB to return a Profissional plan.
    session = MagicMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _stub_active_profissional(session: MagicMock) -> None:
    """Make plan_gate._get_active_subscription return ('active', 'profissional')."""
    sub = MagicMock(status="active", current_period_end=None)
    plan = MagicMock(slug="profissional")
    # Subscription+Plan join returns (Subscription, Plan)
    first_result = MagicMock()
    first_result.__getitem__ = lambda self, i: (sub, plan)[i]
    session.execute.return_value.first.return_value = first_result


def _aggregation_rows():
    """Two months × two statuses each — matches the SQL aggregation result shape."""
    def row(bucket, status, cnt, total):
        m = MagicMock()
        m.__getitem__ = lambda self, k: {
            "bucket": bucket, "status": status, "cnt": cnt, "total": total
        }[k]
        return m

    return [
        row(date(2026, 5, 1), "confirmed", 3, 1500.00),
        row(date(2026, 5, 1), "credit_released", 2, 800.00),
        row(date(2026, 5, 1), "failed", 1, 200.00),
        row(date(2026, 4, 1), "confirmed", 5, 2500.00),
        row(date(2026, 4, 1), "credit_released", 4, 1600.00),
    ]


def test_credit_balance_month_aggregation(client):
    tc, session = client
    _stub_active_profissional(session)

    # Subsequent calls (the actual aggregation query) return our rows
    agg_result = MagicMock()
    agg_result.mappings.return_value.all.return_value = _aggregation_rows()
    # First execute() in plan_gate already consumed; chain side_effect for second:
    session.execute.side_effect = [
        session.execute.return_value,  # plan_gate subscription query
        agg_result,                    # credits aggregation query
    ]

    resp = tc.get("/api/v1/credits/balance?period=month&months_back=6")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["period_type"] == "month"
    assert len(body["periods"]) == 2

    may = next(p for p in body["periods"] if p["period"] == "2026-05")
    # generated = confirmed + released = 3+2 = 5 ; total = 1500+800 = 2300
    assert may["generated_count"] == 5
    assert may["generated_total"] == "2300.00"
    assert may["apropriated_count"] == 2
    assert may["apropriated_total"] == "800.00"
    assert may["available_count"] == 3
    assert may["available_total"] == "1500.00"
    assert may["at_risk_count"] == 1
    assert may["at_risk_total"] == "200.00"


def test_credit_balance_empty(client):
    tc, session = client
    _stub_active_profissional(session)
    empty_result = MagicMock()
    empty_result.mappings.return_value.all.return_value = []
    session.execute.side_effect = [session.execute.return_value, empty_result]

    resp = tc.get("/api/v1/credits/balance")
    assert resp.status_code == 200
    assert resp.json() == {"period_type": "month", "periods": []}


def test_credit_csv_export(client):
    tc, session = client
    _stub_active_profissional(session)
    agg_result = MagicMock()
    agg_result.mappings.return_value.all.return_value = _aggregation_rows()
    session.execute.side_effect = [session.execute.return_value, agg_result]

    resp = tc.get("/api/v1/credits/export.csv?period=month")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]
    body = resp.text
    assert "PERIODO;GERADO_QTD" in body
    assert "2026-05" in body
    # generated total para maio = 2300.00
    assert "2300.00" in body


def test_credit_balance_quarter_label(client):
    tc, session = client
    _stub_active_profissional(session)

    def row(bucket, status, cnt, total):
        m = MagicMock()
        m.__getitem__ = lambda self, k: {
            "bucket": bucket, "status": status, "cnt": cnt, "total": total
        }[k]
        return m

    agg_result = MagicMock()
    # Q2 starts at month 4
    agg_result.mappings.return_value.all.return_value = [
        row(date(2026, 4, 1), "confirmed", 10, 5000.00),
    ]
    session.execute.side_effect = [session.execute.return_value, agg_result]

    resp = tc.get("/api/v1/credits/balance?period=quarter")
    assert resp.status_code == 200
    assert resp.json()["periods"][0]["period"] == "2026-Q2"


def test_credit_requires_plan(client):
    """User sem subscription → 403."""
    tc, session = client
    # Override the subscription query: return None
    session.execute.return_value.first.return_value = None

    resp = tc.get("/api/v1/credits/balance")
    assert resp.status_code == 403
    assert "profissional" in resp.json()["detail"].lower()


# ── #258 Fase 2, parte 1 — drill-down por NF + export PDF ─────────────────────

def _doc_row(*, doc_id=None, filename="nfe-123.xml", doc_type="nfe", status="confirmed",
             credit_value="150.00", created_at=None, bucket=None):
    m = MagicMock()
    m.id = doc_id or uuid.uuid4()
    m.original_filename = filename
    m.doc_type = doc_type
    m.split_payment_status = status
    m.fiscal_metadata = {"credit_value": credit_value} if credit_value is not None else {}
    m.created_at = created_at or datetime(2026, 5, 10, tzinfo=timezone.utc)
    m.bucket = bucket or date(2026, 5, 1)
    return m


def test_credit_documents_drilldown_filters_by_period(client):
    tc, session = client
    _stub_active_profissional(session)

    rows_result = MagicMock()
    rows_result.all.return_value = [
        _doc_row(filename="nfe-maio.xml", bucket=date(2026, 5, 1)),
        _doc_row(filename="nfe-abril.xml", bucket=date(2026, 4, 1)),
    ]
    session.execute.side_effect = [session.execute.return_value, rows_result]

    resp = tc.get("/api/v1/credits/documents?period=2026-05&period_type=month")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["original_filename"] == "nfe-maio.xml"
    assert body[0]["credit_value"] == "150.00"


def test_credit_documents_drilldown_quarter_label(client):
    tc, session = client
    _stub_active_profissional(session)

    rows_result = MagicMock()
    rows_result.all.return_value = [
        _doc_row(filename="nfe-q2.xml", bucket=date(2026, 4, 1)),
    ]
    session.execute.side_effect = [session.execute.return_value, rows_result]

    resp = tc.get("/api/v1/credits/documents?period=2026-Q2&period_type=quarter")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_credit_documents_drilldown_empty_period(client):
    tc, session = client
    _stub_active_profissional(session)

    rows_result = MagicMock()
    rows_result.all.return_value = [_doc_row(bucket=date(2026, 5, 1))]
    session.execute.side_effect = [session.execute.return_value, rows_result]

    resp = tc.get("/api/v1/credits/documents?period=2026-06&period_type=month")
    assert resp.status_code == 200
    assert resp.json() == []


def test_credit_export_pdf_returns_downloadable_file(client):
    """PDF ou fallback HTML (WeasyPrint pode não estar disponível no ambiente de
    teste) — o endpoint deve sempre devolver um arquivo anexável com trilha por NF."""
    tc, session = client
    _stub_active_profissional(session)

    balance_result = MagicMock()
    balance_result.mappings.return_value.all.return_value = [
        {"bucket": date(2026, 5, 1), "status": "confirmed", "cnt": 1, "total": 150.00},
    ]
    docs_result = MagicMock()
    docs_result.all.return_value = [_doc_row(filename="nfe-auditavel.xml", bucket=date(2026, 5, 1))]

    tenant = MagicMock(name="Empresa Teste")
    tenant.name = "Empresa Teste"

    session.execute.side_effect = [session.execute.return_value, balance_result, docs_result]
    session.get.return_value = tenant

    resp = tc.get("/api/v1/credits/export.pdf?period=month&months_back=6")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/pdf") or resp.headers["content-type"].startswith("text/html")
    assert "attachment" in resp.headers["content-disposition"]
    assert len(resp.content) > 0
