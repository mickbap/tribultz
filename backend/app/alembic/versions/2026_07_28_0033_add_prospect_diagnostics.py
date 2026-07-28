"""add_prospect_diagnostics — diagnóstico gratuito p/ prospecção direta (Escopo A)

Ferramenta interna (superadmin): sobe 10-20 XMLs de um escritório contábil
prospect e gera um PDF auditável, sem que o prospect precise ter conta.
Tenant.prospect_diagnostic_id rastreia qual diagnóstico originou um cadastro
via ?diag= no link do PDF (mesmo padrão não-bloqueante do Partner/RFC-0025).

Revision ID: 2026_07_28_0033
Revises: 2026_07_28_0032
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_07_28_0033"
down_revision = "2026_07_28_0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prospect_diagnostics",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("office_name", sa.String(length=200), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("invoice_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        "tenants",
        sa.Column(
            "prospect_diagnostic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("prospect_diagnostics.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "prospect_diagnostic_id")
    op.drop_table("prospect_diagnostics")
