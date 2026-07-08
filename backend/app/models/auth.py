from sqlalchemy import (
    Column,
    String,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name = Column(String(200), nullable=False)
    slug = Column(String(100), nullable=False, unique=True)
    is_active = Column(Boolean, nullable=False, default=True)
    pedagogical_mode_2026 = Column(Boolean, nullable=False, server_default="TRUE")
    # Proveniência comercial (RFC-0025): quem apresentou esta empresa à Tribultz.
    # Opcional, permanente, um só Partner. ondelete=RESTRICT: Partner nunca é
    # apagado enquanto houver empresa vinculada (integridade referencial).
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.id", ondelete="RESTRICT"),
        nullable=True,
    )
    # Using server_default=func.now() for creation
    # Using onupdate=func.now() to ensure python-side updates trigger the timestamp update
    # Schema just says DEFAULT now(), so DB side auto-update depends on triggers (not present in standard schema dump).
    # Application-side `onupdate` ensures correctness.
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True), 
        nullable=False, 
        server_default=func.now(), 
        onupdate=func.now()
    )


class User(Base):
    __tablename__ = "users"

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
    email = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String(50), nullable=False, default="user")
    cnpj = Column(String(18), nullable=True)
    phone = Column(String(20), nullable=True)
    account_type = Column(String(20), nullable=False, default="empresa")  # empresa | contador
    is_active = Column(Boolean, nullable=False, default=True)
    lgpd_consent_at = Column(DateTime(timezone=True), nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String(500), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="users_tenant_id_email_key"),)


class UserTenant(Base):
    __tablename__ = "user_tenants"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    role = Column(String(50), nullable=False, default="user")
    is_default = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="user_tenants_user_tenant_key"),)
