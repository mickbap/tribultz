"""Add api_keys table.

API Keys para acesso à API pública pay-per-call (issue #175).
100 créditos grátis na criação. Compra adicional via Asaas (fase 2).

Revision ID: 2026_05_17_0016
Revises: 2026_05_01_0015
Create Date: 2026-05-17
"""

from alembic import op

revision = "2026_05_17_0016"
down_revision = "2026_05_01_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name            TEXT NOT NULL,
            key_hash        TEXT NOT NULL UNIQUE,
            key_prefix      TEXT NOT NULL,
            credits_balance INTEGER NOT NULL DEFAULT 100,
            is_active       BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at    TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user    ON api_keys(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant  ON api_keys(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash    ON api_keys(key_hash) WHERE is_active = TRUE")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_api_keys_hash")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_tenant")
    op.execute("DROP INDEX IF EXISTS idx_api_keys_user")
    op.execute("DROP TABLE IF EXISTS api_keys")
