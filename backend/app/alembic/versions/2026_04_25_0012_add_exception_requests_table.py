"""Add exception_requests table.

Tabela de exceções fiscais — operador abre exceção em um finding,
informa nome/e-mail de um "admin" responsável, e o sistema notifica esse
admin por e-mail (informativo). Decisão (APPROVED/REJECTED) ocorre dentro
do app, autenticada — sem role-based formal por enquanto.

Revision ID: 2026_04_25_0012
Revises: 2026_04_15_0011
Create Date: 2026-04-25
"""

from alembic import op


revision = "2026_04_25_0012"
down_revision = "2026_04_15_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS exception_requests (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_id           UUID REFERENCES jobs(id) ON DELETE SET NULL,
            finding_id       TEXT NOT NULL,
            rule_id          TEXT NOT NULL,
            justification    TEXT NOT NULL,
            status           TEXT NOT NULL DEFAULT 'OPEN'
                             CHECK (status IN ('OPEN', 'APPROVED', 'REJECTED')),
            admin_name       TEXT NOT NULL,
            admin_email      TEXT NOT NULL,
            created_by       TEXT NOT NULL,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            decided_by       TEXT,
            decided_at       TIMESTAMPTZ,
            decision_comment TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_exception_requests_tenant ON exception_requests(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_exception_requests_status ON exception_requests(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_exception_requests_job ON exception_requests(job_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_exception_requests_job")
    op.execute("DROP INDEX IF EXISTS idx_exception_requests_status")
    op.execute("DROP INDEX IF EXISTS idx_exception_requests_tenant")
    op.execute("DROP TABLE IF EXISTS exception_requests")
