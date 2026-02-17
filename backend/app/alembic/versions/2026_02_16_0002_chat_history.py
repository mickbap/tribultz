"""chat history

Revision ID: 2026_02_16_0002
Revises: 2026_02_16_0001
Create Date: 2026-02-16 19:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_02_16_0002'
down_revision = '2026_02_16_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Table: conversations ─────────────────────────────────────────
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('idx_conversations_tenant_user'), 'conversations', ['tenant_id', 'user_id'], unique=False)

    # ── Table: messages ──────────────────────────────────────────────
    op.create_table(
        'messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),  # "user", "assistant"
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE')
    )
    op.create_index(op.f('idx_messages_conversation'), 'messages', ['conversation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('idx_messages_conversation'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('idx_conversations_tenant_user'), table_name='conversations')
    op.drop_table('conversations')
