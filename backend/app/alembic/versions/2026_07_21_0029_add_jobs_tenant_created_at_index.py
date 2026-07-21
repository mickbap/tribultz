"""add_jobs_tenant_created_at_index — suporte ao relatório de padrão de risco (#442)

O endpoint GET /api/v1/compliance/risk-patterns agrega findings de `jobs.result`
(JSONB) por tenant + janela de data (jsonb_array_elements + GROUP BY). Sem
índice em (tenant_id, created_at), o filtro de período faz sequential scan
sobre `created_at` depois do índice de tenant_id — igual ao que já acontecia
(sem índice) no fallback realtime de compliance.py. Aditivo, idempotente.

Revision ID: 2026_07_21_0029
Revises: 2026_07_19_0028
Create Date: 2026-07-21
"""

from alembic import op

revision = "2026_07_21_0029"
down_revision = "2026_07_19_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant_created_at ON jobs(tenant_id, created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_tenant_created_at")
