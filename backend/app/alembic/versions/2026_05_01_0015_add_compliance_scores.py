"""Add compliance_scores table.

Score mensal de conformidade CBS/IBS por tenant.
Calculado pela task Celery `compute_compliance_score` no primeiro dia de cada mês.

Revision ID: 2026_05_01_0015
Revises: 2026_05_01_0014
Create Date: 2026-05-01
"""

from alembic import op

revision = "2026_05_01_0015"
down_revision = "2026_05_01_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_scores (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            period            TEXT NOT NULL,
            score_pct         NUMERIC(5,2) NOT NULL DEFAULT 0,
            nfs_ok            INTEGER NOT NULL DEFAULT 0,
            nfs_total         INTEGER NOT NULL DEFAULT 0,
            findings_error    INTEGER NOT NULL DEFAULT 0,
            findings_warning  INTEGER NOT NULL DEFAULT 0,
            findings_info     INTEGER NOT NULL DEFAULT 0,
            credit_at_risk    NUMERIC(14,2) NOT NULL DEFAULT 0,
            computed_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, period)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_compliance_tenant ON compliance_scores(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_compliance_period ON compliance_scores(tenant_id, period DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_compliance_period")
    op.execute("DROP INDEX IF EXISTS idx_compliance_tenant")
    op.execute("DROP TABLE IF EXISTS compliance_scores")
