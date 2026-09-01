"""ProspectSuppression — lista de supressão da prospecção comercial direta
(PO-2026-07-SALES-001, Fase 1).

Registros com status opt_out, cliente ou hard_bounce jamais podem reaparecer
com a chave suprimida em uma lista gerada — regra dura, aplicada
incondicionalmente em suppression.py, sem flag de CLI para desativar.
Casamento por cnpj_basico, e-mail exato OU email_domain.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base

# Status suportados. opt_out/cliente/hard_bounce = exclusão dura e
# incondicional; lead_ativo/desqualificado = exclusão por padrão no seletor
# legado. O dry-run de marketing considera qualquer suppression canônica.
SUPPRESSION_STATUSES: tuple[str, ...] = (
    "opt_out",
    "cliente",
    "lead_ativo",
    "desqualificado",
    "hard_bounce",
)


class ProspectSuppression(Base):
    __tablename__ = "prospect_suppressions"
    __table_args__ = (
        CheckConstraint(
            "cnpj_basico IS NOT NULL OR email IS NOT NULL OR email_domain IS NOT NULL",
            name="ck_prospect_suppressions_has_key",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    cnpj_basico = Column(String(8), nullable=True)
    email = Column(String(255), nullable=True)
    email_domain = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False)
    reason = Column(Text, nullable=True)
    source = Column(String(32), nullable=False, default="tribultz", server_default="tribultz")
    source_event_id = Column(String(128), nullable=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
