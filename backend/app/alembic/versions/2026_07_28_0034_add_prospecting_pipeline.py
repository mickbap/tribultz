"""add_prospecting_pipeline — schema da Fase 1 do pipeline de prospecção comercial
direta (PO-2026-07-SALES-001)

Três tabelas: prospect_orgs (registro consolidado por CNPJ básico), prospect_suppressions
(lista de supressão permanente) e prospect_scoring_runs (histórico append-only de
execuções, com versão/checksum de rubrica — suporta reprocessamento futuro sem migration
nova). Ferramenta interna (tools/prospecting/), sem superfície de API nesta fase.

Revision ID: 2026_07_28_0034
Revises: 2026_07_28_0033
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_07_28_0034"
down_revision = "2026_07_28_0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prospect_orgs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("cnpj_basico", sa.String(length=8), nullable=False),
        sa.Column("porte", sa.String(length=2), nullable=False),
        sa.Column("opcao_mei", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("opcao_simples", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("capital_social", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("situacao_cadastral", sa.String(length=2), nullable=False),
        sa.Column("data_inicio_atividade", sa.Date(), nullable=True),
        sa.Column("qtd_socios", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("qtd_estabelecimentos", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uf", sa.String(length=2), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("email_domain", sa.String(length=255), nullable=True),
        sa.Column("email_domain_category", sa.String(length=20), nullable=True),
        sa.Column("cnpj_matriz", sa.String(length=14), nullable=False),
        sa.Column("razao_social", sa.String(length=200), nullable=False),
        sa.Column("nome_fantasia", sa.String(length=200), nullable=True),
        sa.Column("municipio_codigo", sa.String(length=7), nullable=True),
        sa.Column("municipio_nome", sa.String(length=120), nullable=True),
        sa.Column("logradouro", sa.String(length=200), nullable=True),
        sa.Column("numero", sa.String(length=20), nullable=True),
        sa.Column("complemento", sa.String(length=200), nullable=True),
        sa.Column("bairro", sa.String(length=100), nullable=True),
        sa.Column("cep", sa.String(length=8), nullable=True),
        sa.Column("ddd_telefone1", sa.String(length=4), nullable=True),
        sa.Column("telefone1", sa.String(length=20), nullable=True),
        sa.Column("cnae_principal", sa.String(length=7), nullable=False),
        sa.Column("cnaes_secundarios", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("data_situacao_cadastral", sa.Date(), nullable=True),
        sa.Column("dedup_status", sa.String(length=16), nullable=False, server_default="unique"),
        sa.Column("merged_into_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("pre_score", sa.Integer(), nullable=True),
        sa.Column("pre_score_tier", sa.String(length=1), nullable=True),
        sa.Column("pre_score_rubric_version", sa.String(length=32), nullable=True),
        sa.Column("pre_scored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_dump_reference", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("uq_prospect_orgs_cnpj_basico", "prospect_orgs", ["cnpj_basico"])
    op.create_foreign_key(
        "fk_prospect_orgs_merged_into_id", "prospect_orgs", "prospect_orgs",
        ["merged_into_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_prospect_orgs_email_domain", "prospect_orgs", ["email_domain"])
    op.create_index("ix_prospect_orgs_uf", "prospect_orgs", ["uf"])
    op.create_index("ix_prospect_orgs_pre_score", "prospect_orgs", ["pre_score"])
    op.create_index("ix_prospect_orgs_dedup_status", "prospect_orgs", ["dedup_status"])

    op.create_table(
        "prospect_suppressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("cnpj_basico", sa.String(length=8), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("email_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "cnpj_basico IS NOT NULL OR email IS NOT NULL OR email_domain IS NOT NULL",
            name="ck_prospect_suppressions_has_key",
        ),
    )
    op.create_index("ix_prospect_suppressions_cnpj_basico", "prospect_suppressions", ["cnpj_basico"])
    op.create_index("ix_prospect_suppressions_email_domain", "prospect_suppressions", ["email_domain"])
    op.create_index("ix_prospect_suppressions_email", "prospect_suppressions", ["email"])

    op.create_table(
        "prospect_scoring_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("rubric_version", sa.String(length=32), nullable=False),
        sa.Column("rubric_checksum", sa.String(length=64), nullable=False),
        sa.Column("source_dump_reference", sa.String(length=32), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("output_uri", sa.String(length=500), nullable=False),
        sa.Column("output_checksum", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="completed"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("run_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("run_finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prospect_scoring_runs_rubric_version", "prospect_scoring_runs", ["rubric_version"])
    op.create_index("ix_prospect_scoring_runs_created_at", "prospect_scoring_runs", ["created_at"])


def downgrade() -> None:
    op.drop_table("prospect_scoring_runs")
    op.drop_table("prospect_suppressions")
    op.drop_constraint("fk_prospect_orgs_merged_into_id", "prospect_orgs", type_="foreignkey")
    op.drop_table("prospect_orgs")
