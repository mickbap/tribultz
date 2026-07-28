"""Direito de arrependimento de 7 dias (CDC art. 49) no /cancel — Escopo 4
do go-live de billing.

Cancelamento dentro de 7 dias da primeira assinatura do usuário deve
reembolsar integralmente e revogar acesso na hora; depois dos 7 dias,
comportamento padrão (sem reembolso, acesso até o fim do período).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.billing import Payment, Plan, Subscription
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


@pytest.fixture()
def client(db_session):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _user_with_confirmed_subscription(session, *, subscription_created_at, period_end=None):
    tenant = Tenant(name="Empresa Cancelamento Teste", slug=f"cancel-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"cancel-{uuid.uuid4()}@test.com",
        full_name="Usuário Cancelamento",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="admin",
        account_type="empresa",
        email_verified=True,
    )
    session.add(user)
    session.flush()

    plan = session.execute(select(Plan).where(Plan.slug == "starter")).scalar_one()
    sub = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        asaas_customer_id="cus_withdrawal_001",
        current_period_start=subscription_created_at,
        current_period_end=period_end or (subscription_created_at + timedelta(days=30)),
    )
    session.add(sub)
    session.flush()
    # created_at tem server_default — força a data desejada explicitamente
    session.execute(
        Subscription.__table__.update()
        .where(Subscription.id == sub.id)
        .values(created_at=subscription_created_at)
    )

    payment = Payment(
        tenant_id=tenant.id,
        subscription_id=sub.id,
        asaas_payment_id=f"pay_withdrawal_{uuid.uuid4().hex[:8]}",
        amount_cents=4990,
        status="confirmed",
        payment_method="pix",
        paid_at=subscription_created_at,
    )
    session.add(payment)
    session.commit()
    session.refresh(user)
    session.refresh(sub)
    return user, tenant, sub, payment


def _login(client, user, tenant):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123", "tenant_slug": tenant.slug},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestCancelWithdrawalWindow:
    def test_cancel_within_7_days_refunds_in_full(self, client, db_session):
        """Assinatura criada há 2 dias — dentro do prazo de reflexão (CDC art. 49)."""
        created_at = datetime.now(timezone.utc) - timedelta(days=2)
        user, tenant, sub, payment = _user_with_confirmed_subscription(
            db_session, subscription_created_at=created_at
        )
        token = _login(client, user, tenant)

        with patch(
            "app.routers.billing.asaas.refund_payment",
            new=AsyncMock(return_value={"status": "REFUNDED"}),
        ) as mock_refund:
            resp = client.post(
                "/api/v1/billing/cancel",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["refunded"] is True
        assert body["refunded_cents"] == 4990

        mock_refund.assert_called_once()
        assert mock_refund.call_args.args[0] == payment.asaas_payment_id

        db_session.expire_all()
        assert db_session.get(Payment, payment.id).status == "refunded"
        reloaded_sub = db_session.get(Subscription, sub.id)
        assert reloaded_sub.status == "cancelled"
        # Acesso revogado na hora — current_period_end não fica no futuro
        assert reloaded_sub.current_period_end <= datetime.now(timezone.utc)

    def test_cancel_after_7_days_no_refund(self, client, db_session):
        """Assinatura antiga (criada há 30 dias, renovada, período atual ainda em
        curso) — fora do prazo de reflexão, comportamento padrão."""
        created_at = datetime.now(timezone.utc) - timedelta(days=30)
        user, tenant, sub, payment = _user_with_confirmed_subscription(
            db_session,
            subscription_created_at=created_at,
            period_end=datetime.now(timezone.utc) + timedelta(days=10),
        )
        token = _login(client, user, tenant)

        with patch(
            "app.routers.billing.asaas.refund_payment", new=AsyncMock()
        ) as mock_refund:
            resp = client.post(
                "/api/v1/billing/cancel",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["refunded"] is False
        assert body["refunded_cents"] == 0
        mock_refund.assert_not_called()

        db_session.expire_all()
        # Pagamento permanece confirmado — não foi estornado
        assert db_session.get(Payment, payment.id).status == "confirmed"
        reloaded_sub = db_session.get(Subscription, sub.id)
        assert reloaded_sub.status == "cancelled"
        # Acesso mantido até o fim do período original (não revogado na hora)
        assert reloaded_sub.current_period_end > datetime.now(timezone.utc)
