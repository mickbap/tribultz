"""add_prospecting_safeguards — auditoria/rastreabilidade da Fase 1 (Ordem
Complementar à PO-2026-07-SALES-001)

prospect_ingestion_runs e prospect_dedup_runs (guarda de sanidade, validação de
layout, trava de sequenciamento); prospect_scoring_runs ganha rubric_snapshot
(pesos completos, não só checksum); prospect_orgs ganha email_type (item 6 —
critério "tipo do e-mail", independente de "domínio do e-mail").

Revision ID: 2026_07_28_0035
Revises: 2026_07_28_0034
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_07_28_0035"
down_revision = "2026_07_28_0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prospect_ingestion_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("dump_reference", sa.String(length=32), nullable=False),
        sa.Column("target_cnaes", postgresql.JSONB(), nullable=False),
        sa.Column("download_date", sa.Date(), nullable=False),
        sa.Column("total_estabelecimentos_scanned", sa.Integer(), nullable=True),
        sa.Column("total_target_cnae_found", sa.Integer(), nullable=True),
        sa.Column("total_ativas", sa.Integer(), nullable=True),
        sa.Column("total_consolidated", sa.Integer(), nullable=True),
        sa.Column("tolerance_params", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("file_count", sa.Integer(), nullable=True),
        sa.Column("files_sha256", postgresql.JSONB(), nullable=True),
        sa.Column("layout_signature", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="running"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prospect_ingestion_runs_dump_reference", "prospect_ingestion_runs", ["dump_reference"])
    op.create_index("ix_prospect_ingestion_runs_status", "prospect_ingestion_runs", ["status"])
    op.create_index("ix_prospect_ingestion_runs_finished_at", "prospect_ingestion_runs", ["finished_at"])

    op.create_table(
        "prospect_dedup_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("groups_merged", sa.Integer(), nullable=True),
        sa.Column("orgs_merged", sa.Integer(), nullable=True),
        sa.Column("domains_skipped_too_large", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="completed"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_prospect_dedup_runs_finished_at", "prospect_dedup_runs", ["finished_at"])

    op.add_column(
        "prospect_scoring_runs",
        sa.Column("rubric_snapshot", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "prospect_orgs",
        sa.Column("email_type", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prospect_orgs", "email_type")
    op.drop_column("prospect_scoring_runs", "rubric_snapshot")
    op.drop_table("prospect_dedup_runs")
    op.drop_table("prospect_ingestion_runs")
