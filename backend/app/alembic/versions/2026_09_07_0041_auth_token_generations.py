"""Single-use password reset and session invalidation (SEC-01 / #744).

Revision ID: 2026_09_07_0041
Revises: 2026_09_01_0040

Transition: tokens issued before this migration have no generation claim and
are treated as generation zero. They remain usable until the first reset-link
issuance or password change/reset; atomic consumption then advances the stored
generation and rejects every replay or older token.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2026_09_07_0041"
down_revision = "2026_09_01_0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("password_reset_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "password_reset_version")
    op.drop_column("users", "session_version")
