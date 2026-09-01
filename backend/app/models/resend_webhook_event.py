"""Ledger idempotente dos eventos recebidos do Resend (#733)."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from app.database import Base


class ResendWebhookEvent(Base):
    __tablename__ = "resend_webhook_events"
    __table_args__ = (
        UniqueConstraint("svix_id", name="uq_resend_webhook_events_svix_id"),
    )

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    svix_id = Column(String(128), nullable=False)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    email_id = Column(String(128), nullable=True)
    recipient_email = Column(String(320), nullable=True)
    payload_raw = Column(JSONB, nullable=False)
    status = Column(String(16), nullable=False, default="received")
    error = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    applied_at = Column(DateTime(timezone=True), nullable=True)
