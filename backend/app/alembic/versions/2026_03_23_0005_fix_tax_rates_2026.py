"""Fix CBS/IBS reference rates for 2026 test period.

Previous rates (0.0925 CBS, 0.1200 IBS) were PIS/COFINS-era values.
Correct rates per NT 2025.002-RTC: CBS 0.90% (0.0090), IBS 0.10% (0.0010).

Revision ID: 0005
Revises: 0004
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE tax_rules
        SET rate = 0.0090,
            description = 'Aliquota CBS teste 2026 (0.90%)'
        WHERE rule_code = 'STD_CBS'
    """)
    op.execute("""
        UPDATE tax_rules
        SET rate = 0.0010,
            description = 'Aliquota IBS teste 2026 (0.10%)'
        WHERE rule_code = 'STD_IBS'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE tax_rules
        SET rate = 0.0925,
            description = 'Aliquota padrão CBS 2026'
        WHERE rule_code = 'STD_CBS'
    """)
    op.execute("""
        UPDATE tax_rules
        SET rate = 0.1200,
            description = 'Aliquota padrão IBS 2026'
        WHERE rule_code = 'STD_IBS'
    """)
