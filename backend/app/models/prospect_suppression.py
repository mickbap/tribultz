"""ProspectSuppression — lista de supressão da prospecção comercial direta
(PO-2026-07-SALES-001, Fase 1).

Registros com status opt_out ou cliente jamais podem reaparecer em uma lista gerada —
regra dura, aplicada incondicionalmente em suppression.py, sem flag de CLI para
desativar. Casamento por cnpj_basico OU email_domain (não exige as duas colunas).
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base

# Status suportados (PO-2026-07-SALES-001). opt_out/cliente = exclusão dura e
# incondicional; lead_ativo/desqualificado = exclusão por padrão mas configurável
# via --suppress-statuses; hard_bounce = não exclui por padrão (ver suppression.py).
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
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
