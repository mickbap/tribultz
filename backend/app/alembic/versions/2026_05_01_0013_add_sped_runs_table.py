"""Add sped_ingestion_runs table.

Armazena metadados de cada ingestão de arquivo SPED Fiscal,
ligada a um job assíncrono. O resultado detalhado fica no jobs.result.

Revision ID: 2026_05_01_0013
Revises: 2026_04_25_0012
Create Date: 2026-05-01
"""

from alembic import op

revision = "2026_05_01_0013"
down_revision = "2026_04_25_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sped_ingestion_runs (
            id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id            UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_id               UUID REFERENCES jobs(id) ON DELETE SET NULL,
            original_filename    TEXT NOT NULL,
            file_size            BIGINT,
            storage_key          TEXT,
            periodo_ini          DATE,
            periodo_fim          DATE,
            cnpj_empresa         TEXT,
            nome_empresa         TEXT,
            total_produtos       INTEGER NOT NULL DEFAULT 0,
            produtos_conformes   INTEGER NOT NULL DEFAULT 0,
            produtos_divergentes INTEGER NOT NULL DEFAULT 0,
            status               TEXT NOT NULL DEFAULT 'PENDING'
                                 CHECK (status IN ('PENDING','RUNNING','SUCCESS','FAILED')),
            created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_sped_runs_tenant ON sped_ingestion_runs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sped_runs_job ON sped_ingestion_runs(job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_sped_runs_status ON sped_ingestion_runs(tenant_id, status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sped_runs_status")
    op.execute("DROP INDEX IF EXISTS idx_sped_runs_job")
    op.execute("DROP INDEX IF EXISTS idx_sped_runs_tenant")
    op.execute("DROP TABLE IF EXISTS sped_ingestion_runs")
