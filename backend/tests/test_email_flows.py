"""Integration tests — Email Service & Identity Flows.

Covers:
  EMAIL TEMPLATES (unit):
    ✓ verify_email.html renders with user_name and verify_url
    ✓ password_reset.html renders with reset_url and 30-min warning
    ✓ payment_confirmed.html renders with plan_name, amount, features

  PASSWORD RESET FLOW (integration — real DB + TestClient):
    ✓ POST /auth/forgot-password returns 200 for known user
    ✓ POST /auth/forgot-password returns 200 for unknown user (no enumeration)
    ✓ POST /auth/reset-password with valid 30-min token → password updated
    ✓ POST /auth/reset-password with expired/invalid token → 400
    ✓ POST /auth/reset-password with password < 8 chars → 400
    ✓ POST /auth/reset-password with wrong-purpose token → 400

  EMAIL SERVICE (unit):
    ✓ send_verification_email returns True when SMTP disabled (dev mode)
    ✓ send_password_reset_email returns True when SMTP disabled
    ✓ send_payment_confirmation_email returns True when SMTP disabled
    ✓ Amount formatting: 14900 → R$ 149,00
    ✓ Payment method label: pix → PIX, credit_card → Cartão de Crédito

  TOKEN SECURITY:
    ✓ Password reset token expires in <= 30 min
    ✓ Email verification token expires in <= 24 h
    ✓ Reset token does not validate as verification token (purpose isolation)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.security import (
    create_email_verification_token,
    create_password_reset_token,
    get_password_hash,
    verify_password,
    verify_password_reset_token,
)
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.services.email_service import (
    _render,
    send_payment_confirmation_email,
    send_password_reset_email,
    send_verification_email,
)

# ── Test DB ───────────────────────────────────────────────────────

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


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(db_session):
    """Seed an active, verified user for auth flow tests."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Email Test Ltda",
        slug=f"email-test-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"reset-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=get_password_hash("OldPassword@123"),
        full_name="Usuário Reset Teste",
        is_active=True,
        role="user",
        account_type="empresa",
        email_verified=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


# ── Template rendering tests ──────────────────────────────────────


class TestEmailTemplates:
    """Verify Jinja2 templates render correctly with expected variables."""

    def test_verify_email_template_contains_link(self):
        html = _render(
            "verify_email.html",
            user_name="Maria Silva",
            verify_url="https://www.tribultz.com.br/verify-email?token=abc123",
            frontend_url="https://www.tribultz.com.br",
        )
        assert "Maria Silva" in html
        assert "https://www.tribultz.com.br/verify-email?token=abc123" in html
        assert "24 horas" in html
        assert "Confirmar email" in html

    def test_password_reset_template_contains_link_and_warning(self):
        html = _render(
            "password_reset.html",
            user_name="João Contador",
            reset_url="https://www.tribultz.com.br/reset-password?token=xyz",
            frontend_url="https://www.tribultz.com.br",
        )
        assert "João Contador" in html
        assert "https://www.tribultz.com.br/reset-password?token=xyz" in html
        assert "30 minutos" in html
        assert "Redefinir senha" in html

    def test_payment_confirmed_template_renders_receipt(self):
        html = _render(
            "payment_confirmed.html",
            user_name="Carlos Fiscal",
            plan_name="Profissional",
            amount="R$ 149,00",
            payment_method="PIX",
            features=["Motor CBS/IBS", "Memória de Precedentes"],
            console_url="https://www.tribultz.com.br/dashboard",
            frontend_url="https://www.tribultz.com.br",
        )
        assert "Carlos Fiscal" in html
        assert "Profissional" in html
        assert "R$ 149,00" in html
        assert "PIX" in html
        assert "Motor CBS/IBS" in html
        assert "Memória de Precedentes" in html
        assert "Confirmado" in html


# ── Email service unit tests ──────────────────────────────────────


class TestEmailServiceDevMode:
    """When SMTP is disabled, all send_* functions must return True (graceful dev mode)."""

    def test_send_verification_email_returns_true_in_dev(self):
        with patch.object(settings, "EMAIL_VERIFICATION_ENABLED", False):
            result = send_verification_email(
                to_email="dev@test.com",
                user_name="Dev User",
                token="fake-token",
            )
        assert result is True

    def test_send_password_reset_email_returns_true_in_dev(self):
        with patch.object(settings, "EMAIL_VERIFICATION_ENABLED", False):
            result = send_password_reset_email(
                to_email="dev@test.com",
                user_name="Dev User",
                token="fake-token",
            )
        assert result is True

    def test_send_payment_confirmation_returns_true_in_dev(self):
        with patch.object(settings, "EMAIL_VERIFICATION_ENABLED", False):
            result = send_payment_confirmation_email(
                to_email="dev@test.com",
                user_name="Dev User",
                plan_name="Profissional",
                amount_cents=14900,
                payment_method="pix",
            )
        assert result is True

    def test_amount_formatting_cents_to_brl(self):
        """14900 cents → R$ 149,00 (Brazilian decimal format)."""
        with patch.object(settings, "EMAIL_VERIFICATION_ENABLED", False):
            # Confirm the function runs without error and formats correctly
            # by inspecting via a mock on _send_email
            captured = {}

            def _mock_send(to_email, subject, html_body, text_body, log_url):
                captured["html"] = html_body
                return True

            with patch("app.services.email_service._send_email", side_effect=_mock_send):
                send_payment_confirmation_email(
                    to_email="x@x.com",
                    user_name="Test",
                    plan_name="Starter",
                    amount_cents=4990,
                    payment_method="pix",
                )

        assert "49,90" in captured.get("html", ""), "R$ 49,90 expected in HTML"

    def test_payment_method_labels(self):
        """Payment method codes map to human-readable labels in the email."""
        captured = {}

        def _mock_send(to_email, subject, html_body, text_body, log_url):
            captured["html"] = html_body
            return True

        with patch("app.services.email_service._send_email", side_effect=_mock_send):
            send_payment_confirmation_email(
                to_email="x@x.com",
                user_name="Test",
                plan_name="P",
                amount_cents=100,
                payment_method="credit_card",
            )
        assert "Cartão de Crédito" in captured.get("html", "")


# ── Token security tests ──────────────────────────────────────────


class TestTokenSecurity:
    def test_reset_token_expires_within_30_min(self):
        token = create_password_reset_token("user-id-123")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALG],
        )
        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - now
        # Must expire within 30 minutes (with a 10-second tolerance)
        assert delta <= timedelta(minutes=30, seconds=10), f"Token expires too far: {delta}"
        assert delta > timedelta(minutes=0), "Token must not be already expired"

    def test_verification_token_expires_within_24_h(self):
        token = create_email_verification_token("user-id-456")
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALG],
        )
        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        delta = exp - now
        assert delta <= timedelta(hours=24, seconds=10)
        assert delta > timedelta(hours=23)

    def test_reset_token_rejected_as_verification_token(self):
        """A password reset token must NOT be accepted as an email verification token."""
        reset_token = create_password_reset_token("user-id-789")
        # Try to use it as a verification token — must return None
        result = __import__(
            "app.core.security", fromlist=["verify_email_verification_token"]
        ).verify_email_verification_token(reset_token)
        assert result is None, "Reset token must not pass as verification token"

    def test_verification_token_rejected_as_reset_token(self):
        verification_token = create_email_verification_token("user-id-abc")
        result = verify_password_reset_token(verification_token)
        assert result is None, "Verification token must not pass as reset token"

    def test_tampered_token_rejected(self):
        token = create_password_reset_token("user-id-xyz")
        tampered = token[:-4] + "XXXX"
        assert verify_password_reset_token(tampered) is None


# ── Password reset flow integration tests ─────────────────────────


class TestForgotPasswordEndpoint:
    """forgot-password tests bypass the rate limiter (module-level singleton)."""

    @pytest.fixture(autouse=True)
    def bypass_forgot_rate_limit(self):
        """Reset _forgot_limiter in-memory store before each test so the
        module-level singleton (limit=3) never carries state across tests."""
        with patch("app.routers.auth._forgot_limiter.check_or_raise", return_value=None):
            yield

    def test_returns_200_for_known_user(self, client, test_user):
        with patch("app.routers.auth.send_password_reset_email", return_value=True) as mock_send:
            resp = client.post(
                "/api/v1/auth/forgot-password",
                json={"email": test_user.email},
            )
        assert resp.status_code == 200
        assert "link" in resp.json()["message"].lower() or "email" in resp.json()["message"].lower()
        mock_send.assert_called_once()

    def test_returns_200_for_unknown_email_no_enumeration(self, client, db_session):
        """Always 200 — no way to tell if email exists (security requirement)."""
        resp = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@nonexistent-domain-xyz.com"},
        )
        assert resp.status_code == 200

    def test_token_sent_contains_correct_user_id(self, client, test_user):
        captured_token: list[str] = []

        def _capture(to_email, user_name, token):
            captured_token.append(token)
            return True

        with patch("app.routers.auth.send_password_reset_email", side_effect=_capture):
            client.post("/api/v1/auth/forgot-password", json={"email": test_user.email})

        assert len(captured_token) == 1
        user_id = verify_password_reset_token(captured_token[0])
        assert user_id == str(test_user.id)


class TestResetPasswordEndpoint:
    def test_valid_token_updates_password(self, client, db_session, test_user):
        token = create_password_reset_token(str(test_user.id))
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "NewSecure@999"},
        )
        assert resp.status_code == 200
        assert "sucesso" in resp.json()["message"].lower()

        # Verify password was actually changed in DB
        db_session.expire_all()
        updated_user = db_session.get(User, test_user.id)
        assert verify_password("NewSecure@999", str(updated_user.password_hash))
        assert not verify_password("OldPassword@123", str(updated_user.password_hash))

    def test_invalid_token_returns_400(self, client):
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not.a.valid.jwt", "new_password": "NewPass@123"},
        )
        assert resp.status_code == 400
        assert "expirado" in resp.json()["detail"].lower() or "inválido" in resp.json()["detail"].lower()

    def test_short_password_returns_400(self, client, test_user):
        token = create_password_reset_token(str(test_user.id))
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "short"},
        )
        assert resp.status_code == 400
        assert "8" in resp.json()["detail"]

    def test_wrong_purpose_token_returns_400(self, client, test_user):
        """An email verification token must not be accepted as a reset token."""
        verification_token = create_email_verification_token(str(test_user.id))
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": verification_token, "new_password": "NewPass@123"},
        )
        assert resp.status_code == 400

    def test_expired_token_returns_400(self, client, test_user):
        """Manually forge an already-expired token."""
        now = datetime.now(timezone.utc)
        payload = {
            "exp": now - timedelta(minutes=1),  # already expired
            "iat": now - timedelta(minutes=35),
            "sub": str(test_user.id),
            "purpose": "password_reset",
        }
        expired_token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)
        resp = client.post(
            "/api/v1/auth/reset-password",
            json={"token": expired_token, "new_password": "NewPass@123"},
        )
        assert resp.status_code == 400
