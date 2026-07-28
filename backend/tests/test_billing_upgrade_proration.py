"""Proporcionalidade no upgrade de plano (Escopo 3.2 do go-live de billing).

Cobrança do primeiro pagamento após upgrade deve descontar o crédito pelos
dias não usados do plano anterior — sem isso, o cliente paga o valor cheio
do novo plano em cima do que já pagou pelo período corrente do antigo.
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
from app.models.billing import Plan, Subscription
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


def _user_with_subscription(session, *, plan_slug: str, period_end):
    """Cria tenant + user (com CNPJ) + subscription ativa no plano informado.

    period_end=None simula assinatura sem período corrente (ex.: trial) —
    caso em que não há crédito a proporcionalizar.
    """
    tenant = Tenant(name="Empresa Upgrade Teste", slug=f"upg-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"upgrade-{uuid.uuid4()}@test.com",
        full_name="Usuário Upgrade",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="admin",
        account_type="empresa",
        cnpj="11.222.333/0001-81",
        email_verified=True,
    )
    session.add(user)
    session.flush()

    plan = session.execute(select(Plan).where(Plan.slug == plan_slug)).scalar_one()
    sub = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        asaas_customer_id="cus_existing_001",
        current_period_start=datetime.now(timezone.utc) - timedelta(days=15),
        current_period_end=period_end,
    )
    session.add(sub)
    session.commit()
    session.refresh(user)
    return user, tenant, plan


def _login(client, user, tenant):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123", "tenant_slug": tenant.slug},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


class TestUpgradeProration:
    def test_upgrade_with_remaining_period_charges_prorated_amount(self, client, db_session):
        """Starter (R$49,90) → Profissional (R$149,00), 15 dias restantes de 30:
        crédito = 4990 * 15 // 30 = 2495; cobrança = 14900 - 2495 = 12405.
        +1h de margem: `.days` trunca, e o tempo real decorrido entre criar a
        fixture e o endpoint calcular `now` não pode derrubar 15 para 14."""
        period_end = datetime.now(timezone.utc) + timedelta(days=15, hours=1)
        user, tenant, _old_plan = _user_with_subscription(
            db_session, plan_slug="starter", period_end=period_end
        )
        token = _login(client, user, tenant)

        with (
            patch("app.routers.billing.asaas.cancel_subscription", new=AsyncMock(return_value={})),
            patch(
                "app.routers.billing.asaas.create_payment",
                new=AsyncMock(return_value={"id": "pay_prorated_001"}),
            ) as mock_create_payment,
            patch(
                "app.routers.billing.asaas.create_subscription",
                new=AsyncMock(return_value={"id": "sub_new_001"}),
            ) as mock_create_subscription,
            patch(
                "app.routers.billing.asaas.get_pix_qr_code",
                new=AsyncMock(return_value={"encodedImage": "b64img", "payload": "pix-copy-paste"}),
            ),
        ):
            resp = client.post(
                "/api/v1/billing/upgrade",
                json={"plan_slug": "profissional", "billing_type": "PIX"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["prorated"] is True
        assert body["amount_charged_cents"] == 12405

        # Cobrança avulsa criada com o valor proporcional, não o valor cheio
        mock_create_payment.assert_called_once()
        assert mock_create_payment.call_args.kwargs["value"] == pytest.approx(124.05)

        # Assinatura recorrente criada a valor cheio, com next_due_date no fim do período antigo
        mock_create_subscription.assert_called_once()
        sub_kwargs = mock_create_subscription.call_args.kwargs
        assert sub_kwargs["value"] == pytest.approx(149.00)
        assert sub_kwargs["next_due_date"] == period_end.strftime("%Y-%m-%d")

    def test_upgrade_without_remaining_period_charges_full_price(self, client, db_session):
        """Sem current_period_end (ex.: trial) — sem crédito, cobra o valor cheio
        e usa o primeiro pagamento auto-gerado pela assinatura (comportamento
        anterior à proporcionalidade)."""
        user, tenant, _old_plan = _user_with_subscription(
            db_session, plan_slug="trial", period_end=None
        )
        token = _login(client, user, tenant)

        with (
            patch("app.routers.billing.asaas.cancel_subscription", new=AsyncMock(return_value={})),
            patch(
                "app.routers.billing.asaas.create_subscription",
                new=AsyncMock(return_value={"id": "sub_new_002"}),
            ) as mock_create_subscription,
            patch(
                "app.routers.billing.asaas.get_subscription_payments",
                new=AsyncMock(return_value=[{"id": "pay_full_001"}]),
            ),
            patch(
                "app.routers.billing.asaas.get_pix_qr_code",
                new=AsyncMock(return_value={"encodedImage": "b64img", "payload": "pix-copy-paste"}),
            ),
            patch("app.routers.billing.asaas.create_payment", new=AsyncMock()) as mock_create_payment,
        ):
            resp = client.post(
                "/api/v1/billing/upgrade",
                json={"plan_slug": "starter", "billing_type": "PIX"},
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["prorated"] is False
        assert body["amount_charged_cents"] == 4990

        mock_create_payment.assert_not_called()
        sub_kwargs = mock_create_subscription.call_args.kwargs
        assert "next_due_date" not in sub_kwargs or sub_kwargs.get("next_due_date") is None
