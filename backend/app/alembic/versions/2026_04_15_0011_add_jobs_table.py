"""Add jobs table managed by Alembic.

Replaces the runtime DDL (CREATE TABLE IF NOT EXISTS) that ran on every
request in app/routers/jobs.py. The table may already exist in production,
so all operations use IF NOT EXISTS / IF EXISTS for idempotency.

Revision ID: 2026_04_15_0011
Revises: 2026_04_11_0010
Create Date: 2026-04-15
"""

from alembic import op

revision = "2026_04_15_0011"
down_revision = "2026_04_11_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_type        VARCHAR(100) NOT NULL,
            status          VARCHAR(30)  NOT NULL DEFAULT 'QUEUED',
            idempotency_key VARCHAR(200),
            payload         JSONB NOT NULL DEFAULT '{}',
            result          JSONB,
            error_message   TEXT,
            created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT uq_jobs_tenant_idempotency UNIQUE (tenant_id, idempotency_key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_status")
    op.execute("DROP INDEX IF EXISTS idx_jobs_tenant")
    op.execute("DROP TABLE IF EXISTS jobs")
