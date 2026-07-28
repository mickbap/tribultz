"""add_terms_consent_ip — aceite de Termos + IP do consentimento (go-live billing, Escopo 4.2)

`lgpd_consent_at` já existia mas o backend nunca de fato checava o valor
enviado pelo cliente (`data.lgpd_consent`) — o timestamp era gravado
incondicionalmente. Correção: schema Pydantic ganha validator (já existia
para lgpd_consent, adicionado agora para terms_accepted também), e o
momento do aceite passa a registrar o IP de origem.

Revision ID: 2026_07_28_0031
Revises: 2026_07_28_0030
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_07_28_0031"
down_revision = "2026_07_28_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("consent_ip", sa.String(length=45), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "consent_ip")
    op.drop_column("users", "terms_accepted_at")
