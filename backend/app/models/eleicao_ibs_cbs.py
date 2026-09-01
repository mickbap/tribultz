"""Fatos auditáveis da eleição IBS/CBS de optantes do Simples Nacional.

O estado vigente não é persistido: ele é derivado para a data consultada pelo
resolvedor em ``app.services.eleicao_ibs_cbs``. Isso preserva a distinção entre
manifestação, eficácia e cancelamento.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.database import Base


class ManifestacaoEleicaoIBSCBS(Base):
    __tablename__ = "manifestacoes_eleicao_ibs_cbs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    cnpj: Mapped[str] = mapped_column(String(14), nullable=False)

    # Não existe manifestação positiva simétrica pelo regime único. A linha
    # registra opção pelo regular ou renúncia a uma opção regular anterior.
    tipo_manifestacao: Mapped[str] = mapped_column(String(32), nullable=False)
    manifestada_em: Mapped[date] = mapped_column(Date, nullable=False)
    modalidade: Mapped[str] = mapped_column(String(48), nullable=False)
    eficacia_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    eficacia_fim: Mapped[date] = mapped_column(Date, nullable=False)

    cancelada_em: Mapped[date | None] = mapped_column(Date, nullable=True)
    fonte: Mapped[str] = mapped_column(String(160), nullable=False)
    evidencia_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    cancelamento_fonte: Mapped[str | None] = mapped_column(String(160), nullable=True)
    cancelamento_evidencia_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "tipo_manifestacao IN ('OPCAO_REGIME_REGULAR', 'RENUNCIA_REGIME_REGULAR')",
            name="ck_manifestacoes_eleicao_ibs_cbs_tipo",
        ),
        CheckConstraint(
            "modalidade = 'SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR'",
            name="ck_manifestacoes_eleicao_ibs_cbs_modalidade",
        ),
        CheckConstraint(
            "eficacia_inicio <= eficacia_fim",
            name="ck_manifestacoes_eleicao_ibs_cbs_eficacia",
        ),
        CheckConstraint(
            "cancelada_em IS NULL OR cancelada_em >= manifestada_em",
            name="ck_manifestacoes_eleicao_ibs_cbs_cancelamento_data",
        ),
        CheckConstraint(
            "(cancelada_em IS NULL AND cancelamento_fonte IS NULL "
            "AND cancelamento_evidencia_ref IS NULL) OR "
            "(cancelada_em IS NOT NULL AND cancelamento_fonte IS NOT NULL "
            "AND cancelamento_evidencia_ref IS NOT NULL)",
            name="ck_manifestacoes_eleicao_ibs_cbs_cancelamento_evidencia",
        ),
        Index(
            "ix_manifestacoes_eleicao_ibs_cbs_empresa_data",
            "tenant_id",
            "cnpj",
            "manifestada_em",
        ),
    )
