"""Eleição temporal IBS/CBS para optantes do Simples Nacional (#731).

Revision ID: 2026_09_01_0039
Revises: 2026_08_16_0038
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_09_01_0039"
down_revision = "2026_08_16_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manifestacoes_eleicao_ibs_cbs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("cnpj", sa.String(length=14), nullable=False),
        sa.Column("tipo_manifestacao", sa.String(length=32), nullable=False),
        sa.Column("manifestada_em", sa.Date(), nullable=False),
        sa.Column("modalidade", sa.String(length=48), nullable=False),
        sa.Column("eficacia_inicio", sa.Date(), nullable=False),
        sa.Column("eficacia_fim", sa.Date(), nullable=False),
        sa.Column("cancelada_em", sa.Date(), nullable=True),
        sa.Column("fonte", sa.String(length=160), nullable=False),
        sa.Column("evidencia_ref", sa.String(length=500), nullable=False),
        sa.Column("cancelamento_fonte", sa.String(length=160), nullable=True),
        sa.Column("cancelamento_evidencia_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "tipo_manifestacao IN ('OPCAO_REGIME_REGULAR', 'RENUNCIA_REGIME_REGULAR')",
            name="ck_manifestacoes_eleicao_ibs_cbs_tipo",
        ),
        sa.CheckConstraint(
            "modalidade = 'SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR'",
            name="ck_manifestacoes_eleicao_ibs_cbs_modalidade",
        ),
        sa.CheckConstraint(
            "eficacia_inicio <= eficacia_fim",
            name="ck_manifestacoes_eleicao_ibs_cbs_eficacia",
        ),
        sa.CheckConstraint(
            "cancelada_em IS NULL OR cancelada_em >= manifestada_em",
            name="ck_manifestacoes_eleicao_ibs_cbs_cancelamento_data",
        ),
        sa.CheckConstraint(
            "(cancelada_em IS NULL AND cancelamento_fonte IS NULL "
            "AND cancelamento_evidencia_ref IS NULL) OR "
            "(cancelada_em IS NOT NULL AND cancelamento_fonte IS NOT NULL "
            "AND cancelamento_evidencia_ref IS NOT NULL)",
            name="ck_manifestacoes_eleicao_ibs_cbs_cancelamento_evidencia",
        ),
    )
    op.create_index(
        "ix_manifestacoes_eleicao_ibs_cbs_empresa_data",
        "manifestacoes_eleicao_ibs_cbs",
        ["tenant_id", "cnpj", "manifestada_em"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_manifestacoes_eleicao_ibs_cbs_empresa_data",
        table_name="manifestacoes_eleicao_ibs_cbs",
    )
    op.drop_table("manifestacoes_eleicao_ibs_cbs")
