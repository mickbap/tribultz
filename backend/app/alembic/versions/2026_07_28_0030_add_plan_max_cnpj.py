"""add_plan_max_cnpj — limite numérico de CNPJs por plano (go-live billing, Escopo 3.5)

`has_multi_cnpj` (booleano) nunca foi de fato enforced em código — a página
/pricing já promete números específicos por plano ("1 CNPJ", "Até 10 CNPJs",
"Até 50 CNPJs") que não tinham nenhum campo numérico correspondente. Mapeamento
confirmado com o Techlead (28/07/2026): Trial/Starter/Profissional=1,
Empresarial=10, Contador=50 — bate com o texto já publicado em cada plano.

Revision ID: 2026_07_28_0030
Revises: 2026_07_21_0029
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_07_28_0030"
down_revision = "2026_07_21_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plans",
        sa.Column("max_cnpj", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute("""
        UPDATE plans SET max_cnpj = 1 WHERE slug IN ('trial', 'starter', 'profissional');
        UPDATE plans SET max_cnpj = 10 WHERE slug = 'empresarial';
        UPDATE plans SET max_cnpj = 50 WHERE slug = 'contador';
    """)


def downgrade() -> None:
    op.drop_column("plans", "max_cnpj")
