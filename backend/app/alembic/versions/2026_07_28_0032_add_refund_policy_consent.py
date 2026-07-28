"""add_refund_policy_consent — aceite da Política de Reembolso (go-live billing, Escopo 4.2/#4)

Terceiro documento a exigir aceite explícito no /register, ao lado de
lgpd_consent e terms_accepted (mesma migration series, 2026_07_28_0031).

Revision ID: 2026_07_28_0032
Revises: 2026_07_28_0031
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_07_28_0032"
down_revision = "2026_07_28_0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("refund_policy_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "refund_policy_accepted_at")
