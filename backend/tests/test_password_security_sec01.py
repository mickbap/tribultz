"""SEC-01 integration coverage with HTTP and real PostgreSQL persistence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import delete, select

from app.config import settings
from app.core.security import get_password_hash
from app.database import SessionLocal
from app.main import app
from app.models.auth import Tenant, User
from app.routers.auth import _forgot_limiter, _login_limiter


OLD_PASSWORD = "OldPassword@123"
NEW_PASSWORD = "NewPassword@456"


@pytest.fixture(autouse=True)
def auth_boundaries():
    """Keep the test at HTTP/DB boundaries while replacing external controls."""
    app.dependency_overrides.clear()
    with (
        patch.object(_login_limiter, "check_or_raise", return_value=None),
        patch.object(_forgot_limiter, "check_or_raise", return_value=None),
        patch("app.routers.auth.verify_captcha", new=AsyncMock(return_value=True)),
    ):
        yield
    app.dependency_overrides.clear()


@pytest.fixture
def http_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def persisted_user():
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    email = f"sec01-{uuid.uuid4().hex}@test.tribultz"

    with SessionLocal.begin() as db:
        db.add(
            Tenant(
                id=tenant_id,
                name="SEC-01 Tenant",
                slug=f"sec01-{uuid.uuid4().hex}",
            )
        )
        db.add(
            User(
                id=user_id,
                tenant_id=tenant_id,
                email=email,
                full_name="SEC-01 User",
                password_hash=get_password_hash(OLD_PASSWORD),
                role="admin",
                account_type="empresa",
                is_active=True,
                email_verified=True,
            )
        )

    yield SimpleNamespace(id=user_id, tenant_id=tenant_id, email=email)

    with SessionLocal.begin() as db:
        db.execute(delete(Tenant).where(Tenant.id == tenant_id))


def _login(client: TestClient, email: str, password: str):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, "captcha_token": "test"},
    )


def _reset_token(client: TestClient, email: str) -> str:
    captured: list[str] = []

    def capture_email(*, to_email: str, user_name: str, token: str) -> bool:
        assert to_email == email
        assert user_name
        captured.append(token)
        return True

    with patch("app.routers.auth.send_password_reset_email", side_effect=capture_email):
        response = client.post("/api/v1/auth/forgot-password", json={"email": email})

    assert response.status_code == 200
    assert len(captured) == 1
    return captured[0]


def _auth_header(login_response) -> dict[str, str]:
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _protected_request(client: TestClient, headers: dict[str, str]):
    return client.get("/api/v1/auth/settings/tenant", headers=headers)


def test_reset_is_single_use_invalidates_old_session_and_allows_new_login(
    http_client: TestClient,
    persisted_user,
):
    old_session = _auth_header(_login(http_client, persisted_user.email, OLD_PASSWORD))
    token = _reset_token(http_client, persisted_user.email)

    first = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": NEW_PASSWORD},
    )
    replay = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "AnotherPassword@789"},
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    assert _protected_request(http_client, old_session).status_code == 401
    assert _login(http_client, persisted_user.email, OLD_PASSWORD).status_code == 401
    assert _login(http_client, persisted_user.email, NEW_PASSWORD).status_code == 200


def test_concurrent_reset_has_at_most_one_success(http_client: TestClient, persisted_user):
    token = _reset_token(http_client, persisted_user.email)

    def consume() -> int:
        with TestClient(app) as client:
            return client.post(
                "/api/v1/auth/reset-password",
                json={"token": token, "new_password": NEW_PASSWORD},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda _: consume(), range(2)))

    assert statuses.count(200) == 1
    assert statuses.count(400) == 1
    assert _login(http_client, persisted_user.email, NEW_PASSWORD).status_code == 200


def test_new_reset_request_invalidates_older_reset_token(
    http_client: TestClient,
    persisted_user,
):
    older = _reset_token(http_client, persisted_user.email)
    newer = _reset_token(http_client, persisted_user.email)

    rejected = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": older, "new_password": NEW_PASSWORD},
    )
    accepted = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": newer, "new_password": NEW_PASSWORD},
    )

    assert rejected.status_code == 400
    assert accepted.status_code == 200


def test_change_password_invalidates_session_and_pending_reset_token(
    http_client: TestClient,
    persisted_user,
):
    old_session = _auth_header(_login(http_client, persisted_user.email, OLD_PASSWORD))
    reset_before_change = _reset_token(http_client, persisted_user.email)

    changed = http_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": OLD_PASSWORD, "new_password": NEW_PASSWORD},
        headers=old_session,
    )

    assert changed.status_code == 200
    assert _protected_request(http_client, old_session).status_code == 401
    assert http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": reset_before_change, "new_password": "AnotherPassword@789"},
    ).status_code == 400
    assert _login(http_client, persisted_user.email, NEW_PASSWORD).status_code == 200


def test_legacy_generation_zero_token_transitions_to_single_use(
    http_client: TestClient,
    persisted_user,
):
    """Pre-deploy tokens omit the version claim and map to initial version zero."""
    now = datetime.now(timezone.utc)
    legacy_token = jwt.encode(
        {
            "exp": now + timedelta(minutes=30),
            "iat": now,
            "sub": str(persisted_user.id),
            "purpose": "password_reset",
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALG,
    )

    first = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": legacy_token, "new_password": NEW_PASSWORD},
    )
    replay = http_client.post(
        "/api/v1/auth/reset-password",
        json={"token": legacy_token, "new_password": "AnotherPassword@789"},
    )

    assert first.status_code == 200
    assert replay.status_code == 400
    with SessionLocal() as db:
        user = db.execute(select(User).where(User.id == persisted_user.id)).scalar_one()
        assert cast(int, user.password_reset_version) == 1
        assert cast(int, user.session_version) == 1
