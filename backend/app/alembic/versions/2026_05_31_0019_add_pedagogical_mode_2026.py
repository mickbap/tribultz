"""add_pedagogical_mode_2026

Adiciona flag pedagogical_mode_2026 à tabela tenants.

Quando True (padrão): findings de obrigação acessória CBS/IBS são
downgraded de FATAL para WARNING, com badge "Período Pedagógico LC 214
art. 348" e nota de 60 dias para sanar sem multa.

Referência legal: art. 348, §§ 3º e 4º, da LC 214/2025 (incluídos pela LC 227/2026).

Revision ID: 2026_05_31_0019
Revises: 2026_05_31_0018
Create Date: 2026-05-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2026_05_31_0019"
down_revision = "2026_05_31_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "pedagogical_mode_2026",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "pedagogical_mode_2026")
