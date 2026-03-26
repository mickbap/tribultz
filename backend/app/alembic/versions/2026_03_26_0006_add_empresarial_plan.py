"""add empresarial plan between profissional and contador

Revision ID: 2026_03_26_0006
Revises: 2026_03_23_0005
Create Date: 2026-03-26
"""

from alembic import op

revision = "2026_03_26_0006"
down_revision = "2026_03_23_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add plano Empresarial ────────────────────────────────────
    # Positioned between Profissional (R$149) and Contador (R$349)
    # Profissional + controle de filiais (até 10 CNPJs)
    op.execute("""
        INSERT INTO plans (slug, name, price_cents, max_validations, max_ai_messages,
                           has_pdf_reports, has_batch, has_dashboard, has_api_access,
                           has_multi_cnpj, trial_days)
        VALUES
            ('empresarial', 'Empresarial', 24900, 2000, NULL, TRUE, TRUE, TRUE, TRUE, TRUE, NULL)
        ON CONFLICT (slug) DO UPDATE
            SET name          = EXCLUDED.name,
                price_cents   = EXCLUDED.price_cents,
                max_validations = EXCLUDED.max_validations,
                has_pdf_reports = EXCLUDED.has_pdf_reports,
                has_batch       = EXCLUDED.has_batch,
                has_dashboard   = EXCLUDED.has_dashboard,
                has_api_access  = EXCLUDED.has_api_access,
                has_multi_cnpj  = EXCLUDED.has_multi_cnpj;
    """)


def downgrade() -> None:
    op.execute("DELETE FROM plans WHERE slug = 'empresarial'")
