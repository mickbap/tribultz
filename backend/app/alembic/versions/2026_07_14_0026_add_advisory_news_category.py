"""add Advisory category to news check constraint

Revision ID: 2026_07_14_0026
Revises: 2026_07_08_0025
Create Date: 2026-07-14
"""
from alembic import op

revision = "2026_07_14_0026"
down_revision = "2026_07_08_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("news_category_check", "news", type_="check")
    op.create_check_constraint(
        "news_category_check",
        "news",
        "category IN ('Feature', 'Fix', 'Security', 'Advisory')",
    )


def downgrade() -> None:
    op.drop_constraint("news_category_check", "news", type_="check")
    op.create_check_constraint(
        "news_category_check",
        "news",
        "category IN ('Feature', 'Fix', 'Security')",
    )
