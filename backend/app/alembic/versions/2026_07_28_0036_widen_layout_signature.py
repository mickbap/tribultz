"""widen_layout_signature — corrige bug de dimensionamento da fatia 1 (Ordem
Complementar)

A assinatura real ("empresas:7campos;estabelecimentos:30campos;simples:7campos;
socios:11campos") tem ~74 caracteres, maior que o VARCHAR(64) original —
descoberto ao rodar o teste fim-a-fim contra as fixtures reais. Corrige para
TEXT (sem limite arbitrário) em vez de recalcular um novo limite fixo.

Revision ID: 2026_07_28_0036
Revises: 2026_07_28_0035
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_07_28_0036"
down_revision = "2026_07_28_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "prospect_ingestion_runs", "layout_signature",
        existing_type=sa.String(length=64), type_=sa.Text(), nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "prospect_ingestion_runs", "layout_signature",
        existing_type=sa.Text(), type_=sa.String(length=64), nullable=True,
    )
