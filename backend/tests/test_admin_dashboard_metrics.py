"""Métricas novas do admin dashboard — assinantes ativos por plano + churn
(Escopo 5.2, go-live de billing)."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant, User
from app.models.billing import Plan, Subscription
from app.core.security import get_password_hash
from app.routers.admin import _active_plan_distribution, _churn_rate_month

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


def _make_subscription(session, *, plan_slug, status, cancelled_at=None):
    tenant = Tenant(name="Empresa Métricas Teste", slug=f"metrics-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()

    user = User(
        email=f"metrics-{uuid.uuid4()}@test.com",
        full_name="Usuário Métricas",
        password_hash=get_password_hash("password123"),
        tenant_id=tenant.id,
        role="admin",
        account_type="empresa",
        email_verified=True,
    )
    session.add(user)
    session.flush()

    plan = session.execute(select(Plan).where(Plan.slug == plan_slug)).scalar_one()
    sub = Subscription(
        tenant_id=tenant.id,
        user_id=user.id,
        plan_id=plan.id,
        status=status,
        cancelled_at=cancelled_at,
    )
    session.add(sub)
    session.commit()
    return sub


class TestActivePlanDistribution:
    def test_counts_only_active_subscriptions(self, db_session):
        _make_subscription(db_session, plan_slug="starter", status="active")
        _make_subscription(db_session, plan_slug="starter", status="cancelled")
        _make_subscription(db_session, plan_slug="starter", status="trial")
        _make_subscription(db_session, plan_slug="profissional", status="active")

        result = {row["plan"]: row["count"] for row in _active_plan_distribution(db_session)}

        assert result.get("starter") == 1
        assert result.get("profissional") == 1


class TestChurnRateMonth:
    def test_churn_rate_counts_cancellations_this_month(self, db_session):
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # 1 cancelado este mês, 1 cancelado no mês passado (não deve contar)
        _make_subscription(
            db_session, plan_slug="starter", status="cancelled",
            cancelled_at=now - timedelta(days=1),
        )
        _make_subscription(
            db_session, plan_slug="starter", status="cancelled",
            cancelled_at=month_start - timedelta(days=5),
        )

        cancelled_month, rate = _churn_rate_month(db_session, month_start, active_count=9)

        assert cancelled_month == 1
        assert rate == pytest.approx(10.0)  # 1 / (9 + 1) * 100

    def test_churn_rate_zero_when_no_subscribers(self, db_session):
        cancelled_month, rate = _churn_rate_month(
            db_session, datetime.now(timezone.utc), active_count=0
        )
        assert cancelled_month == 0
        assert rate == 0.0
