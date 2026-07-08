"""add_founding_partners — camada de licenciamento (RFC-0017 + ADR-0008)

Grant Adapter dos Founding Partners:
- ``early_adopters``: empresa admitida no programa (RF001).
- ``early_grants``: autorização operacional (plano + vigência), sem assinatura
  ASAAS. Nunca representa pagamento. ondelete: RESTRICT para tenants (histórico
  preservado), CASCADE de grant → early_adopter.

Revision ID: 2026_07_08_0025
Revises: 2026_07_08_0024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_07_08_0025"
down_revision = "2026_07_08_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "early_adopters",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("empresa", sa.String(length=200), nullable=False),
        sa.Column("cnpj", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("responsavel", sa.String(length=200), nullable=True),
        sa.Column("telefone", sa.String(length=32), nullable=True),
        sa.Column("origem", sa.String(length=32), nullable=False, server_default="outro"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT", name="fk_early_adopters_tenant_id"),
    )
    op.create_index("ix_early_adopters_tenant_id", "early_adopters", ["tenant_id"])
    op.create_index("ix_early_adopters_email", "early_adopters", ["email"])

    op.create_table(
        "early_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("early_adopter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_slug", sa.String(length=50), nullable=False, server_default="contador"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("granted_by_email", sa.String(length=255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["early_adopter_id"], ["early_adopters.id"], ondelete="CASCADE", name="fk_early_grants_adopter_id"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="RESTRICT", name="fk_early_grants_tenant_id"),
    )
    # Índice que serve a resolução de licença no login (tenant + janela de vigência).
    op.create_index("ix_early_grants_resolve", "early_grants", ["tenant_id", "status", "ends_at"])


def downgrade() -> None:
    op.drop_index("ix_early_grants_resolve", table_name="early_grants")
    op.drop_table("early_grants")
    op.drop_index("ix_early_adopters_email", table_name="early_adopters")
    op.drop_index("ix_early_adopters_tenant_id", table_name="early_adopters")
    op.drop_table("early_adopters")
