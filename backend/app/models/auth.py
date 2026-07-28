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
    # Atribuição de qual diagnóstico gratuito (prospecção comercial direta)
    # trouxe este cadastro — link ?diag= no PDF (ver auth.py). Opcional,
    # permanente, ondelete=SET NULL: apagar o diagnóstico não deve apagar a
    # Tenant. Não é o rastreio geral de canal/UTM (Escopo B, ainda não construído).
    prospect_diagnostic_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prospect_diagnostics.id", ondelete="SET NULL"),
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
    # Contexto do ator — exatamente um dos dois é preenchido (CHECK
    # ck_users_exactly_one_actor_domain, migration 2026_07_16_0027).
    # tenant_id: ator pertence a uma Empresa (Tenant) — fluxo original.
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    # partner_id: ator é um Partner (Programa de Parceiros, RFC-0026) — nunca
    # um Tenant. Ver Partner em app.models.partner.
    partner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("partners.id", ondelete="CASCADE"),
        nullable=True,
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
    terms_accepted_at = Column(DateTime(timezone=True), nullable=True)
    refund_policy_accepted_at = Column(DateTime(timezone=True), nullable=True)
    # IP no momento do aceite (LGPD + Termos + Reembolso, capturados juntos no
    # /register) — Escopo 4.2 do go-live de billing: data, hora e IP do aceite.
    consent_ip = Column(String(45), nullable=True)  # cabe IPv6
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String(500), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    # Marcados a cada login bem-sucedido (RFC-0024): alimentam "Primeiro/Último
    # login" da jornada do cockpit Early Adopters sem tabela adicional.
    # first_login_at grava só na transição NULL→preenchido; last_login_at sempre.
    first_login_at = Column(DateTime(timezone=True), nullable=True)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
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

    @property
    def actor_type(self) -> str:
        """Domínio do ator autenticado — computado, nunca armazenado.

        Deriva de qual FK está preenchida (garantido mutuamente exclusivo
        pela CHECK constraint ck_users_exactly_one_actor_domain), evitando
        uma coluna redundante que poderia divergir da realidade.
        """
        return "partner" if self.partner_id is not None else "tenant"


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
