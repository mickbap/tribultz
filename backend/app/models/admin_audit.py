"""AdminAuditLog — trilha de auditoria de ações administrativas (Fase 2 do admin)."""

from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from app.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    actor_user_id = Column(UUID(as_uuid=True), nullable=True)
    actor_email = Column(Text, nullable=False)
    action = Column(Text, nullable=False)
    target_type = Column(Text, nullable=False)
    target_id = Column(Text, nullable=True)
    detail = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
