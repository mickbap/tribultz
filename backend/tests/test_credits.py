"""Tests for /api/v1/credits endpoints (#258 Phase 1).

Mocks DB Session and plan-gate (profissional) via dependency_overrides.
"""

from __future__ import annotations

import uuid
from datetime import date
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
