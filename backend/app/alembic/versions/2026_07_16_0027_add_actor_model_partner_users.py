"""add_actor_model_partner_users — generaliza User para múltiplos atores (RFC-0026)

Autenticação passa a representar o ator (Tenant User | Partner), não mais
assumir tenant_id como identidade central. tenant_id vira contexto,
preenchido apenas quando o ator pertence a um Tenant.

- ``users.tenant_id`` vira nullable (era NOT NULL).
- ``users.partner_id`` novo (FK opcional para ``partners``).
- CHECK constraint: exatamente um de (tenant_id, partner_id) não-nulo —
  garante estruturalmente que Partner nunca é Tenant e vice-versa.
- Índice único parcial de e-mail para atores partner (a constraint
  existente ``(tenant_id, email)`` não previne duplicidade quando
  tenant_id é NULL — regra de SQL: NULL não é igual a NULL).

Revision ID: 2026_07_16_0027
Revises: 2026_07_14_0026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_07_16_0027"
down_revision = "2026_07_14_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "tenant_id", nullable=True)

    op.add_column(
        "users",
        sa.Column("partner_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_partner_id",
        "users",
        "partners",
        ["partner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_users_partner_id", "users", ["partner_id"])

    op.create_check_constraint(
        "ck_users_exactly_one_actor_domain",
        "users",
        "(tenant_id IS NOT NULL) != (partner_id IS NOT NULL)",
    )

    op.create_index(
        "uq_users_partner_email",
        "users",
        ["email"],
        unique=True,
        postgresql_where=sa.text("partner_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_users_partner_email", table_name="users")
    op.drop_constraint("ck_users_exactly_one_actor_domain", "users", type_="check")
    op.drop_index("ix_users_partner_id", table_name="users")
    op.drop_constraint("fk_users_partner_id", "users", type_="foreignkey")
    op.drop_column("users", "partner_id")
    op.alter_column("users", "tenant_id", nullable=False)
