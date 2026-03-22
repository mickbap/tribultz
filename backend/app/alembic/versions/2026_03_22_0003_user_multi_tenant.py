"""add user multi-tenant columns and user_tenants table

Revision ID: 2026_03_22_0003
Revises: 2026_02_16_0002
Create Date: 2026-03-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_03_22_0003'
down_revision: Union[str, None] = '2026_02_16_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── New columns on users ──────────────────────────────────────
    op.add_column('users', sa.Column('cnpj', sa.String(length=18), nullable=True))
    op.add_column('users', sa.Column('account_type', sa.String(length=20), server_default='empresa', nullable=False))
    op.add_column('users', sa.Column('lgpd_consent_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), server_default=sa.text('false'), nullable=False))
    op.add_column('users', sa.Column('email_verification_token', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))

    # ── Table: user_tenants (M:N association) ─────────────────────
    op.create_table(
        'user_tenants',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='user', nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'tenant_id', name='user_tenants_user_tenant_key'),
    )


def downgrade() -> None:
    op.drop_table('user_tenants')
    op.drop_column('users', 'deleted_at')
    op.drop_column('users', 'email_verification_token')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'lgpd_consent_at')
    op.drop_column('users', 'account_type')
    op.drop_column('users', 'cnpj')
