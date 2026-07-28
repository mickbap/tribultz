"""ProspectDiagnostic — diagnóstico gratuito para prospecção comercial direta.

Fluxo interno (superadmin): sobe 10-20 XMLs de um escritório contábil
prospect, gera um PDF auditável com o que seria rejeitado hoje e a data em
que a penalidade CBS/IBS passa a valer, sem que o prospect precise ter conta.
O PDF termina com um link de trial atribuído a este diagnóstico
(``?diag=<id>``) — a Tenant que se cadastrar por esse link é vinculada aqui
via ``Tenant.prospect_diagnostic_id`` (ver auth.py, captura não-bloqueante,
mesmo padrão do Partner/RFC-0025).

Não é o mesmo que Partner (RFC-0025): Partner é proveniência de indicação
permanente de um parceiro de referência; isto é a atribuição de UM envio de
diagnóstico específico. Não substitui o rastreio geral de canal/UTM
(Escopo B do plano de aquisição) — é o suporte mínimo para o link do PDF.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class ProspectDiagnostic(Base):
    __tablename__ = "prospect_diagnostics"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    office_name = Column(String(200), nullable=False)
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    invoice_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    storage_key = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
