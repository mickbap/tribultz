"""Billing models — plans, subscriptions, payments, usage tracking."""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    slug = Column(String(50), nullable=False, unique=True)  # trial, starter, profissional, contador
    name = Column(String(100), nullable=False)
    price_cents = Column(Integer, nullable=False, default=0)  # R$49,90 = 4990
    max_validations = Column(Integer, nullable=True)  # NULL = unlimited
    max_ai_messages = Column(Integer, nullable=True)  # NULL = unlimited
    has_pdf_reports = Column(Boolean, nullable=False, default=False)
    has_batch = Column(Boolean, nullable=False, default=False)
    has_dashboard = Column(Boolean, nullable=False, default=False)
    has_api_access = Column(Boolean, nullable=False, default=False)
    has_multi_cnpj = Column(Boolean, nullable=False, default=False)
    max_cnpj = Column(Integer, nullable=False, default=1)  # 1|1|1|10|50 (trial..contador)
    trial_days = Column(Integer, nullable=True)  # 3 for trial, NULL otherwise
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status = Column(String(30), nullable=False, default="trial")  # trial|active|pending|past_due|cancelled|expired
    asaas_subscription_id = Column(String(100), nullable=True)
    asaas_customer_id = Column(String(100), nullable=True)
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Payment(Base):
    __tablename__ = "payments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    asaas_payment_id = Column(String(100), nullable=False, unique=True)  # idempotency key
    amount_cents = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="pending")  # pending|confirmed|refunded|failed
    payment_method = Column(String(20), nullable=False)  # credit_card|pix
    pix_qr_code = Column(Text, nullable=True)  # base64 PNG
    pix_copy_paste = Column(Text, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UsageTracking(Base):
    __tablename__ = "usage_tracking"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    period = Column(String(7), nullable=False)  # YYYY-MM
    validations_used = Column(Integer, nullable=False, default=0)
    ai_messages_used = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "period", name="usage_tracking_user_period_key"),
    )
