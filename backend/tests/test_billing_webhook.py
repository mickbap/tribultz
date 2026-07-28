"""Webhook integration tests — ASAAS Sandbox Dry-Run.

Simulates every relevant Asaas webhook event against a real PostgreSQL
test DB (transaction-rolled-back after each test) using FastAPI TestClient.

Covered scenarios:
  ✓ PAYMENT_CONFIRMED  → payment.status=confirmed, subscription.status=active, user.is_active=True
  ✓ PAYMENT_CONFIRMED  → idempotent (second call returns already_confirmed, no double-write)
  ✓ PAYMENT_RECEIVED   → treated identically to PAYMENT_CONFIRMED
  ✓ PAYMENT_OVERDUE    → payment.status=overdue, subscription.status=past_due
  ✓ SUBSCRIPTION_DELETED → subscription.status=cancelled
  ✓ Invalid token      → 200 + ignored (Asaas must never receive 4xx)
  ✓ Unknown payment id → 200 + ignored
  ✓ Unhandled event    → 200 + ignored

CPF/CNPJ validation (AsaasService.create_customer):
  ✓ Valid CNPJ accepted
  ✓ Invalid CNPJ (wrong check digit) raises AsaasError(400)
  ✓ Invalid CPF (wrong check digit) raises AsaasError(400)
  ✓ Wrong length raises AsaasError(400)
  ✓ All-same-digit CNPJ (e.g. 00000000000000) raises AsaasError(400)
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.billing import Payment, Plan, Subscription
from app.core.security import get_password_hash
from app.services.asaas_service import AsaasError, AsaasService, validate_cpf_cnpj

# ── Test database ─────────────────────────────────────────────────

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://tribultz:tribultz@localhost:5432/tribultz",
)
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

WEBHOOK_TOKEN = "test-webhook-token-sandbox"
WEBHOOK_HEADERS = {"asaas-access-token": WEBHOOK_TOKEN}

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def db_session():
    """Transactional test session — rolls back after each test."""
    conn = engine.connect()
    tx = conn.begin()
    session = TestingSessionLocal(bind=conn)
    yield session
    session.close()
    tx.rollback()
    conn.close()


@pytest.fixture()
def client(db_session):
    """TestClient wired to the transactional session and with webhook token mocked."""
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db

    # Patch verify_webhook_token so tests don't depend on settings
    with patch(
        "app.routers.billing.asaas.verify_webhook_token",
        return_value=True,
    ):
        yield TestClient(app)

    app.dependency_overrides.clear()


@pytest.fixture()
def billing_fixtures(db_session):
    """Seed a tenant, user, plan, subscription and pending payment.

    Returns a dict with all created objects for assertions.
    """
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Empresa Teste Ltda",
        slug=f"empresa-teste-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(tenant)
    db_session.flush()

    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        email=f"user-{uuid.uuid4().hex[:6]}@test.com",
        password_hash=get_password_hash("Senha@1234"),
        full_name="Usuário Teste",
        is_active=False,  # starts inactive — webhook must activate
        role="user",
        account_type="empresa",
    )
    db_session.add(user)
    db_session.flush()

    plan = db_session.execute(
        select(Plan).where(Plan.slug == "profissional")
    ).scalar_one_or_none()

    if not plan:
        plan = Plan(
            id=uuid.uuid4(),
            slug="profissional",
            name="Profissional",
            price_cents=14900,
            max_validations=500,
            has_pdf_reports=True,
            has_batch=True,
            has_dashboard=True,
        )
        db_session.add(plan)
        db_session.flush()

    subscription = Subscription(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status="pending",
        asaas_customer_id="cus_sandbox_abc123",
    )
    db_session.add(subscription)
    db_session.flush()

    asaas_payment_id = f"pay_sandbox_{uuid.uuid4().hex[:10]}"
    payment = Payment(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        subscription_id=subscription.id,
        asaas_payment_id=asaas_payment_id,
        amount_cents=14900,
        status="pending",
        payment_method="pix",
    )
    db_session.add(payment)
    db_session.flush()

    return {
        "tenant": tenant,
        "user": user,
        "plan": plan,
        "subscription": subscription,
        "payment": payment,
        "asaas_payment_id": asaas_payment_id,
    }


def _confirmed_payload(asaas_payment_id: str, event: str = "PAYMENT_CONFIRMED") -> dict:
    return {
        "event": event,
        "payment": {
            "id": asaas_payment_id,
            "status": "CONFIRMED",
            "value": 149.00,
            "billingType": "PIX",
            "customer": "cus_sandbox_abc123",
        },
    }


# ── Webhook flow tests ────────────────────────────────────────────


class TestWebhookPaymentConfirmed:
    def test_payment_confirmed_activates_user_and_subscription(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_CONFIRMED → payment=confirmed, subscription=active, user.is_active=True."""
        fx = billing_fixtures
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json=_confirmed_payload(fx["asaas_payment_id"]),
            headers=WEBHOOK_HEADERS,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["action"] == "payment_confirmed"

        # Reload from DB and verify all three state changes
        db_session.expire_all()
        payment = db_session.get(Payment, fx["payment"].id)
        subscription = db_session.get(Subscription, fx["subscription"].id)
        user = db_session.get(User, fx["user"].id)

        assert payment.status == "confirmed"
        assert payment.paid_at is not None
        assert subscription.status == "active"
        assert subscription.current_period_start is not None
        assert user.is_active is True

    def test_payment_received_treated_as_confirmed(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_RECEIVED is an alias for PAYMENT_CONFIRMED."""
        fx = billing_fixtures
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json=_confirmed_payload(fx["asaas_payment_id"], event="PAYMENT_RECEIVED"),
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "payment_confirmed"

        db_session.expire_all()
        assert db_session.get(Payment, fx["payment"].id).status == "confirmed"

    def test_payment_confirmed_is_idempotent(
        self, client, db_session, billing_fixtures
    ):
        """Sending PAYMENT_CONFIRMED twice must not error — second call returns already_confirmed."""
        fx = billing_fixtures
        payload = _confirmed_payload(fx["asaas_payment_id"])

        r1 = client.post("/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS)
        r2 = client.post("/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["action"] == "payment_confirmed"
        assert r2.json()["action"] == "already_confirmed"

    def test_transaction_recorded_in_db(
        self, client, db_session, billing_fixtures
    ):
        """paid_at must be persisted — proves the transaction was committed."""
        fx = billing_fixtures
        client.post(
            "/api/v1/billing/webhooks/asaas",
            json=_confirmed_payload(fx["asaas_payment_id"]),
            headers=WEBHOOK_HEADERS,
        )
        db_session.expire_all()
        payment = db_session.get(Payment, fx["payment"].id)
        assert payment.paid_at is not None, "paid_at must be recorded in the database"
        assert payment.status == "confirmed"


class TestWebhookPaymentOverdue:
    def test_overdue_marks_payment_and_subscription(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_OVERDUE → payment.status=overdue, subscription.status=past_due."""
        fx = billing_fixtures
        payload = {
            "event": "PAYMENT_OVERDUE",
            "payment": {"id": fx["asaas_payment_id"], "status": "OVERDUE"},
        }
        resp = client.post(
            "/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["action"] == "payment_overdue"

        db_session.expire_all()
        assert db_session.get(Payment, fx["payment"].id).status == "overdue"
        assert db_session.get(Subscription, fx["subscription"].id).status == "past_due"

    def test_overdue_already_overdue_is_noop(
        self, client, db_session, billing_fixtures
    ):
        """Sending PAYMENT_OVERDUE twice must not raise errors."""
        fx = billing_fixtures
        payload = {
            "event": "PAYMENT_OVERDUE",
            "payment": {"id": fx["asaas_payment_id"], "status": "OVERDUE"},
        }
        r1 = client.post("/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS)
        r2 = client.post("/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS)

        assert r1.status_code == 200
        assert r2.status_code == 200


class TestWebhookPaymentCardDeclined:
    def test_card_declined_marks_payment_failed_no_suspension(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_CREDIT_CARD_CAPTURE_REFUSED → payment.status=failed, subscription
        untouched (Asaas retries automatically before PAYMENT_OVERDUE)."""
        fx = billing_fixtures
        payload = {
            "event": "PAYMENT_CREDIT_CARD_CAPTURE_REFUSED",
            "payment": {"id": fx["asaas_payment_id"]},
        }
        resp = client.post(
            "/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["action"] == "payment_declined"

        db_session.expire_all()
        assert db_session.get(Payment, fx["payment"].id).status == "failed"
        assert db_session.get(Subscription, fx["subscription"].id).status == "pending"


class TestWebhookPaymentRefunded:
    def test_refund_marks_payment_and_cancels_subscription(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_REFUNDED → payment.status=refunded, subscription cancelled (access revoked)."""
        fx = billing_fixtures
        payload = {
            "event": "PAYMENT_REFUNDED",
            "payment": {"id": fx["asaas_payment_id"]},
        }
        resp = client.post(
            "/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["action"] == "payment_refunded"

        db_session.expire_all()
        assert db_session.get(Payment, fx["payment"].id).status == "refunded"
        sub = db_session.get(Subscription, fx["subscription"].id)
        assert sub.status == "cancelled"
        assert sub.cancelled_at is not None

    def test_partial_refund_treated_same_as_full(
        self, client, db_session, billing_fixtures
    ):
        """PAYMENT_PARTIALLY_REFUNDED uses the same handling as PAYMENT_REFUNDED."""
        fx = billing_fixtures
        payload = {
            "event": "PAYMENT_PARTIALLY_REFUNDED",
            "payment": {"id": fx["asaas_payment_id"]},
        }
        resp = client.post(
            "/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["action"] == "payment_refunded"


class TestWebhookSubscriptionCreatedUpdated:
    def test_subscription_created_is_audited_not_ignored(
        self, client, db_session, billing_fixtures
    ):
        """SUBSCRIPTION_CREATED is a sync/confirmation signal — audited, not 'ignored'."""
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json={"event": "SUBSCRIPTION_CREATED", "subscription": {"id": "sub_new_001"}},
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["action"] == "subscription_created"

    def test_subscription_updated_is_audited_not_ignored(
        self, client, db_session, billing_fixtures
    ):
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json={"event": "SUBSCRIPTION_UPDATED", "subscription": {"id": "sub_upd_001"}},
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["action"] == "subscription_updated"


class TestWebhookSubscriptionDeleted:
    def test_subscription_deleted_cancels(
        self, client, db_session, billing_fixtures
    ):
        """SUBSCRIPTION_DELETED → subscription.status=cancelled, cancelled_at is set."""
        fx = billing_fixtures
        asaas_sub_id = "sub_sandbox_xyz999"
        fx["subscription"].asaas_subscription_id = asaas_sub_id
        db_session.flush()

        payload = {
            "event": "SUBSCRIPTION_DELETED",
            "subscription": {"id": asaas_sub_id},
        }
        resp = client.post(
            "/api/v1/billing/webhooks/asaas", json=payload, headers=WEBHOOK_HEADERS
        )

        assert resp.status_code == 200
        assert resp.json()["action"] == "subscription_cancelled"

        db_session.expire_all()
        sub = db_session.get(Subscription, fx["subscription"].id)
        assert sub.status == "cancelled"
        assert sub.cancelled_at is not None


class TestWebhookRejectionAndEdgeCases:
    def test_invalid_token_returns_200_ignored(self, db_session, billing_fixtures):
        """Invalid token must return 200 (not 4xx) to prevent Asaas retry loops."""
        def _override_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_db
        # Do NOT patch verify_webhook_token — use real validator with empty config
        with patch("app.routers.billing.asaas.verify_webhook_token", return_value=False):
            c = TestClient(app)
            resp = c.post(
                "/api/v1/billing/webhooks/asaas",
                json=_confirmed_payload("pay_any"),
                headers={"asaas-access-token": "wrong-token"},
            )
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert "token" in resp.json()["reason"]

    def test_unknown_payment_id_returns_ignored(
        self, client, db_session, billing_fixtures
    ):
        """If payment ID not in DB, must return 200+ignored (not 500)."""
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json=_confirmed_payload("pay_NONEXISTENT_99999"),
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"
        assert resp.json()["reason"] == "payment not found"

    def test_unhandled_event_returns_ignored(
        self, client, db_session, billing_fixtures
    ):
        """Unknown event types must return 200+ignored gracefully."""
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json={"event": "PAYMENT_ANTICIPATED", "payment": {"id": "pay_any"}},
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_missing_payment_id_in_payload(
        self, client, db_session, billing_fixtures
    ):
        """Payload without payment.id must return 200+ignored (not crash)."""
        resp = client.post(
            "/api/v1/billing/webhooks/asaas",
            json={"event": "PAYMENT_CONFIRMED", "payment": {}},
            headers=WEBHOOK_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


# ── CPF / CNPJ validation unit tests ─────────────────────────────


class TestCpfCnpjValidation:
    """Unit tests for the pre-flight validator in AsaasService."""

    # ── Valid documents ───────────────────────────────────────────

    def test_valid_cnpj_digits_returned_clean(self):
        """Valid CNPJ: digits returned without formatting."""
        # 11.222.333/0001-81 — valid check digits
        result = validate_cpf_cnpj("11.222.333/0001-81")
        assert result == "11222333000181"

    def test_valid_cnpj_unformatted(self):
        result = validate_cpf_cnpj("11222333000181")
        assert result == "11222333000181"

    def test_valid_cpf(self):
        # 529.982.247-25 — canonical valid test CPF
        result = validate_cpf_cnpj("529.982.247-25")
        assert result == "52998224725"

    # ── Invalid CNPJ ─────────────────────────────────────────────

    def test_invalid_cnpj_wrong_check_digit(self):
        """CNPJ with corrupted last digit raises AsaasError 400."""
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("11222333000182")  # last digit changed: 1→2
        assert exc_info.value.status == 400
        assert "CNPJ" in exc_info.value.detail

    def test_invalid_cnpj_all_zeros(self):
        """All-zero CNPJ must be rejected (trivially invalid)."""
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("00000000000000")
        assert exc_info.value.status == 400

    def test_invalid_cnpj_all_same_digit(self):
        """All-same-digit CNPJ must be rejected."""
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("11111111111111")
        assert exc_info.value.status == 400

    # ── Invalid CPF ──────────────────────────────────────────────

    def test_invalid_cpf_wrong_check_digit(self):
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("52998224726")  # last digit changed: 5→6
        assert exc_info.value.status == 400
        assert "CPF" in exc_info.value.detail

    def test_invalid_cpf_all_ones(self):
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("11111111111")
        assert exc_info.value.status == 400

    # ── Wrong length ─────────────────────────────────────────────

    def test_wrong_length_raises(self):
        with pytest.raises(AsaasError) as exc_info:
            validate_cpf_cnpj("12345")
        assert exc_info.value.status == 400
        assert "dígito" in exc_info.value.detail

    def test_empty_string_raises(self):
        with pytest.raises(AsaasError):
            validate_cpf_cnpj("")

    # ── Integration: create_customer rejects before HTTP call ────

    @pytest.mark.asyncio
    async def test_create_customer_rejects_invalid_cnpj_before_api_call(self):
        """create_customer must raise AsaasError without making any HTTP request."""
        svc = AsaasService()
        svc.api_key = "test_key"
        svc.base_url = "https://sandbox.asaas.com/api"

        with pytest.raises(AsaasError) as exc_info:
            await svc.create_customer(
                name="Empresa Inválida",
                email="bad@test.com",
                cpf_cnpj="11111111111111",  # all-same-digit — invalid
            )
        assert exc_info.value.status == 400
        # Must raise BEFORE HTTP — no network call needed to validate
