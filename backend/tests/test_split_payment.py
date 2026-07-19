"""Tests for /api/v1/split-payment — foco no split IBS/CBS (#486).

Mocks DB Session e plan-gate (profissional) via dependency_overrides, mesmo
padrão de test_credits.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
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
    id=USER_ID, email="techlead@tribultz.com", tenant_id=TENANT_ID,
    full_name="Tech Lead", is_active=True, role="admin", password_hash="x",
)


@pytest.fixture()
def client():
    app.dependency_overrides[get_current_user] = lambda: _mock_user
    session = MagicMock()
    app.dependency_overrides[get_db] = lambda: session
    yield TestClient(app), session
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def _no_grant_result() -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    return result


def _stub_active_profissional(session: MagicMock) -> None:
    sub = MagicMock(status="active", current_period_end=None)
    plan = MagicMock(slug="profissional")
    first_result = MagicMock()
    first_result.__getitem__ = lambda self, i: (sub, plan)[i]
    session.execute.return_value.first.return_value = first_result


def _doc_row(fiscal_metadata: dict, status: str = "pending") -> MagicMock:
    m = MagicMock()
    m.id = uuid.uuid4()
    m.original_filename = "nfe-teste.xml"
    m.doc_type = "nfe"
    m.fiscal_metadata = fiscal_metadata
    m.split_payment_status = status
    m.created_at = datetime(2026, 7, 19, tzinfo=timezone.utc)
    return m


def test_update_status_persiste_ibs_cbs_discriminados(client):
    tc, session = client
    _stub_active_profissional(session)

    doc_id = str(uuid.uuid4())
    existing = _doc_row({})
    updated = _doc_row({"credit_value_ibs": "90.00", "credit_value_cbs": "60.00"}, status="confirmed")

    fetchone_results = [existing, updated]
    session.execute.side_effect = [
        session.execute.return_value,  # plan_gate subscription query
        _no_grant_result(),            # plan_gate grant check (#487)
        MagicMock(fetchone=lambda: fetchone_results[0]),   # SELECT antes do UPDATE
        MagicMock(),                                        # UPDATE
        MagicMock(fetchone=lambda: fetchone_results[1]),    # SELECT após o UPDATE
    ]

    resp = tc.patch(
        f"/api/v1/split-payment/status/{doc_id}",
        json={"status": "confirmed", "credit_value_ibs": "90.00", "credit_value_cbs": "60.00"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["credit_value_ibs"] == "90.00"
    assert body["credit_value_cbs"] == "60.00"
    assert body["credit_value"] == "150.00"  # derivado, #486

    # A UPDATE query (3º execute) deve ter gravado ibs/cbs, sem o combinado legado.
    update_call = session.execute.call_args_list[3]
    import json as _json
    fm_written = _json.loads(update_call.args[1]["fm"])
    assert fm_written["credit_value_ibs"] == "90.00"
    assert fm_written["credit_value_cbs"] == "60.00"
    assert "credit_value" not in fm_written


def test_update_status_legado_continua_funcionando(client):
    """Regressão: PATCH só com credit_value (sem ibs/cbs) continua funcionando
    exatamente como antes do #486."""
    tc, session = client
    _stub_active_profissional(session)

    doc_id = str(uuid.uuid4())
    existing = _doc_row({})
    updated = _doc_row({"credit_value": "150.00"}, status="confirmed")

    fetchone_results = [existing, updated]
    session.execute.side_effect = [
        session.execute.return_value,
        _no_grant_result(),
        MagicMock(fetchone=lambda: fetchone_results[0]),
        MagicMock(),
        MagicMock(fetchone=lambda: fetchone_results[1]),
    ]

    resp = tc.patch(
        f"/api/v1/split-payment/status/{doc_id}",
        json={"status": "confirmed", "credit_value": "150.00"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["credit_value"] == "150.00"
    assert body["credit_value_ibs"] is None
    assert body["credit_value_cbs"] is None
