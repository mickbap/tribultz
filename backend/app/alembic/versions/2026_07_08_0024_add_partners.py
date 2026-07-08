"""add_partners — Partner Attribution v1 (RFC-0025)

Proveniência comercial: quem apresentou cada empresa à Tribultz.
- Cria a tabela ``partners`` (entidade de origem — nunca comissão/contrato/financeiro).
- Adiciona ``tenants.partner_id`` (FK opcional, permanente, um só Partner).
- ondelete=RESTRICT: um Partner nunca é apagado enquanto houver empresa vinculada
  (sem exclusão física — desativação via ``status``).

Revision ID: 2026_07_08_0024
Revises: 2026_07_02_0023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_07_08_0024"
down_revision = "2026_07_02_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "partners",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("type", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_partners_code"),
    )
    op.add_column(
        "tenants",
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tenants_partner_id",
        "tenants",
        "partners",
        ["partner_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_tenants_partner_id", "tenants", ["partner_id"])


def downgrade() -> None:
    op.drop_index("ix_tenants_partner_id", table_name="tenants")
    op.drop_constraint("fk_tenants_partner_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "partner_id")
    op.drop_table("partners")
