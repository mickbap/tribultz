"""Drop cclass_trib_items — tabela vestigial (#365 follow-up).

Desde o #365, a API pública /classtrib lê do classtrib.json (fonte única, igual ao
motor) e ninguém mais lê esta tabela. O único escritor era o task sync_classtrib_svrs,
agora removido (superado pelo scrape público diário → classtrib.json). Esta migration
aposenta a tabela. ClassTribService (lookup/batch_validate) usa a API SVRS, não a tabela —
não é afetado.

Revision ID: 2026_06_30_0022
Revises: 2026_06_26_0021
"""

from alembic import op

revision = "2026_06_30_0022"
down_revision = "2026_06_26_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_descricao")
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_active")
    op.execute("DROP INDEX IF EXISTS idx_cclass_trib_codigo")
    op.execute("DROP TABLE IF EXISTS cclass_trib_items")


def downgrade() -> None:
    # Recria a estrutura (vazia) para reversibilidade do schema. Os dados não retornam —
    # a fonte canônica passou a ser app/data/classtrib.json (#365).
    op.execute("""
        CREATE TABLE IF NOT EXISTS cclass_trib_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            codigo          TEXT NOT NULL UNIQUE,
            descricao       TEXT NOT NULL,
            p_cbs           NUMERIC(8,4) NOT NULL DEFAULT 0,
            p_ibs           NUMERIC(8,4) NOT NULL DEFAULT 0,
            regime_especial TEXT,
            vigencia_ini    DATE,
            vigencia_fim    DATE,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_codigo ON cclass_trib_items(codigo)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_active ON cclass_trib_items(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_cclass_trib_descricao ON cclass_trib_items USING gin(to_tsvector('portuguese', descricao))")
