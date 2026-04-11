"""Drop conversations and chat_messages tables.

The chat feature was discontinued in S22 for security reasons (prompt injection risk)
and financial efficiency. No production data exists.

Revision ID: 2026_04_11_0010
Revises: 2026_03_31_0009
Create Date: 2026-04-11
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "2026_04_11_0010"
down_revision = "2026_03_31_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # chat_messages has FK → conversations; drop child first
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS conversations CASCADE")


def downgrade() -> None:
    # Recreate tables if needed for rollback
    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL,
            user_id     UUID NOT NULL,
            title       TEXT NOT NULL DEFAULT 'Nova conversa',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_tenant_user
        ON conversations (tenant_id, user_id)
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content         TEXT NOT NULL,
            evidence        JSONB,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
