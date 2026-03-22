"""add billing tables: plans, subscriptions, payments, usage_tracking + phone on users

Revision ID: 2026_03_22_0004
Revises: 2026_03_22_0003
Create Date: 2026-03-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2026_03_22_0004'
down_revision: Union[str, None] = '2026_03_22_0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Add phone to users ──────────────────────────────────────
    op.add_column('users', sa.Column('phone', sa.String(length=20), nullable=True))

    # ── Table: plans ────────────────────────────────────────────
    op.create_table(
        'plans',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('price_cents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_validations', sa.Integer(), nullable=True),
        sa.Column('max_ai_messages', sa.Integer(), nullable=True),
        sa.Column('has_pdf_reports', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_batch', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_dashboard', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_api_access', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('has_multi_cnpj', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('trial_days', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='plans_slug_key'),
    )

    # ── Table: subscriptions ────────────────────────────────────
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('plan_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='trial'),
        sa.Column('asaas_subscription_id', sa.String(length=100), nullable=True),
        sa.Column('asaas_customer_id', sa.String(length=100), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trial_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['plans.id'], ondelete='RESTRICT'),
    )
    op.create_index('idx_subscriptions_user', 'subscriptions', ['user_id'])
    op.create_index('idx_subscriptions_tenant', 'subscriptions', ['tenant_id'])
    op.create_index('idx_subscriptions_status', 'subscriptions', ['status'])

    # ── Table: payments ─────────────────────────────────────────
    op.create_table(
        'payments',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('subscription_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('asaas_payment_id', sa.String(length=100), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
        sa.Column('payment_method', sa.String(length=20), nullable=False),
        sa.Column('pix_qr_code', sa.Text(), nullable=True),
        sa.Column('pix_copy_paste', sa.Text(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('asaas_payment_id', name='payments_asaas_payment_id_key'),
    )
    op.create_index('idx_payments_subscription', 'payments', ['subscription_id'])
    op.create_index('idx_payments_tenant', 'payments', ['tenant_id'])
    op.create_index('idx_payments_status', 'payments', ['status'])

    # ── Table: usage_tracking ───────────────────────────────────
    op.create_table(
        'usage_tracking',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('period', sa.String(length=7), nullable=False),
        sa.Column('validations_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ai_messages_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'period', name='usage_tracking_user_period_key'),
    )
    op.create_index('idx_usage_tracking_user', 'usage_tracking', ['user_id'])
    op.create_index('idx_usage_tracking_tenant', 'usage_tracking', ['tenant_id'])

    # ── Seed plans ──────────────────────────────────────────────
    op.execute("""
        INSERT INTO plans (slug, name, price_cents, max_validations, max_ai_messages,
                           has_pdf_reports, has_batch, has_dashboard, has_api_access,
                           has_multi_cnpj, trial_days)
        VALUES
            ('trial',        'Trial',        0,     5,    25, FALSE, FALSE, FALSE, FALSE, FALSE, 3),
            ('starter',      'Starter',      4990,  10,   50, FALSE, FALSE, TRUE,  FALSE, FALSE, NULL),
            ('profissional', 'Profissional', 14900, 500,  NULL, TRUE,  TRUE,  TRUE,  FALSE, FALSE, NULL),
            ('contador',     'Contador',     34900, NULL, NULL, TRUE,  TRUE,  TRUE,  TRUE,  TRUE,  NULL)
        ON CONFLICT (slug) DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table('usage_tracking')
    op.drop_table('payments')
    op.drop_table('subscriptions')
    op.execute("DELETE FROM plans WHERE slug IN ('trial', 'starter', 'profissional', 'contador')")
    op.drop_table('plans')
    op.drop_column('users', 'phone')
