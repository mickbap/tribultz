"""add news changelog table

Revision ID: 2026_03_28_0007
Revises: 2026_03_26_0006
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_03_28_0007"
down_revision = "2026_03_26_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "category IN ('Feature', 'Fix', 'Security')",
            name="news_category_check",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("news")
