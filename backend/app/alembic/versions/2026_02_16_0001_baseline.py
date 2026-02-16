"""baseline

Revision ID: 2026_02_16_0001
Revises: 
Create Date: 2026-02-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2026_02_16_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    # 1. Tenants
    op.create_table('tenants',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug')
    )

    # 2. Users
    op.create_table('users',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='user', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'email', name='users_tenant_id_email_key')
    )
    op.create_index('idx_users_tenant', 'users', ['tenant_id'], unique=False)

    # 3. Companies
    op.create_table('companies',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('cnpj', sa.String(length=18), nullable=False),
        sa.Column('legal_name', sa.String(length=300), nullable=False),
        sa.Column('trade_name', sa.String(length=300), nullable=True),
        sa.Column('state_code', sa.CHAR(length=2), nullable=True),
        sa.Column('city_code', sa.String(length=10), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'cnpj')
    )
    op.create_index('idx_companies_tenant', 'companies', ['tenant_id'], unique=False)

    # 4. Tax Rules
    op.create_table('tax_rules',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('tax_type', sa.String(length=20), nullable=False),
        sa.Column('rate', sa.Numeric(precision=10, scale=4), server_default='0', nullable=False),
        sa.Column('valid_from', sa.Date(), nullable=False),
        sa.Column('valid_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'rule_code', 'valid_from')
    )
    op.create_index('idx_tax_rules_tenant', 'tax_rules', ['tenant_id'], unique=False)
    op.create_index('idx_tax_rules_type', 'tax_rules', ['tenant_id', 'tax_type'], unique=False)

    # 5. NCM Codes
    op.create_table('ncm_codes',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('cbs_rate', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('ibs_rate', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('is_exempt', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code')
    )
    op.create_index('idx_ncm_codes_tenant', 'ncm_codes', ['tenant_id'], unique=False)

    # 6. Invoices
    op.create_table('invoices',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_number', sa.String(length=60), nullable=False),
        sa.Column('invoice_type', sa.String(length=30), server_default='NF-e', nullable=False),
        sa.Column('status', sa.String(length=30), server_default='draft', nullable=False),
        sa.Column('issue_date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('total_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('total_cbs', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('total_ibs', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('total_is', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'company_id', 'invoice_number')
    )
    op.create_index('idx_invoices_company', 'invoices', ['tenant_id', 'company_id'], unique=False)
    op.create_index('idx_invoices_tenant', 'invoices', ['tenant_id'], unique=False)

    # 7. Invoice Items
    op.create_table('invoice_items',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('invoice_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('ncm_code', sa.String(length=10), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=14, scale=4), server_default='1', nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=18, scale=4), server_default='0', nullable=False),
        sa.Column('total_price', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('cbs_rate', sa.Numeric(precision=10, scale=4), server_default='0', nullable=False),
        sa.Column('cbs_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('ibs_rate', sa.Numeric(precision=10, scale=4), server_default='0', nullable=False),
        sa.Column('ibs_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('is_rate', sa.Numeric(precision=10, scale=4), server_default='0', nullable=False),
        sa.Column('is_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_invoice_items_invoice', 'invoice_items', ['invoice_id'], unique=False)
    op.create_index('idx_invoice_items_tenant', 'invoice_items', ['tenant_id'], unique=False)

    # 8. Tax Credits
    op.create_table('tax_credits',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('tax_type', sa.String(length=20), nullable=False),
        sa.Column('credit_amount', sa.Numeric(precision=18, scale=2), server_default='0', nullable=False),
        sa.Column('reference_period', sa.String(length=7), nullable=False),
        sa.Column('origin_invoice_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=30), server_default='pending', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['origin_invoice_id'], ['invoices.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tax_credits_company', 'tax_credits', ['tenant_id', 'company_id'], unique=False)
    op.create_index('idx_tax_credits_tenant', 'tax_credits', ['tenant_id'], unique=False)

    # 9. Audit Log
    op.create_table('audit_log',
        sa.Column('id', sa.UUID(as_uuid=True), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('tenant_id', sa.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.UUID(as_uuid=True), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_audit_log_tenant', 'audit_log', ['tenant_id'], unique=False)

    # Seed Data (Optional, but useful for baseline)
    # Default Tenant
    op.execute("INSERT INTO tenants (name, slug) VALUES ('Default Tenant', 'default') ON CONFLICT (slug) DO NOTHING")
    
    # Standard Rates
    op.execute("""
        INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
        SELECT t.id, 'STD_CBS', 'Aliquota padrão CBS 2026', 'CBS', 0.0925, '2026-01-01'
        FROM tenants t WHERE t.slug = 'default'
        ON CONFLICT DO NOTHING
    """)
    op.execute("""
        INSERT INTO tax_rules (tenant_id, rule_code, description, tax_type, rate, valid_from)
        SELECT t.id, 'STD_IBS', 'Aliquota padrão IBS 2026', 'IBS', 0.1200, '2026-01-01'
        FROM tenants t WHERE t.slug = 'default'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('audit_log')
    op.drop_table('tax_credits')
    op.drop_table('invoice_items')
    op.drop_table('invoices')
    op.drop_table('ncm_codes')
    op.drop_table('tax_rules')
    op.drop_table('companies')
    op.drop_table('users')
    op.drop_table('tenants')
    # op.execute('DROP EXTENSION IF EXISTS pgcrypto') # Usually bad idea to drop extensions in migration
