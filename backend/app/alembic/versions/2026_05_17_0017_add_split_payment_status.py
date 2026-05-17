"""Add split_payment_status to documents.

Revision ID: 2026_05_17_0017
Revises: 2026_05_17_0016
Create Date: 2026-05-17

Split Payment (LC 214 art. 22): o crédito IBS/CBS só é liberado após confirmação
do pagamento do imposto destacado na NF. Este campo rastreia o status por documento.

NULL    = documento não é NF-e com CBS/IBS (não aplicável)
pending = aguardando confirmação do pagamento (Split Payment não processado)
confirmed = imposto pago e confirmado, crédito liberado para uso
credit_released = crédito já apropriado/compensado
failed  = falha ou prazo expirado (crédito em risco)
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_05_17_0017"
down_revision = "2026_05_17_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "split_payment_status",
            sa.String(30),
            nullable=True,
            comment="pending | confirmed | credit_released | failed | NULL=não aplicável",
        ),
    )
    op.create_index(
        "ix_documents_split_payment_status",
        "documents",
        ["split_payment_status"],
        postgresql_where=sa.text("split_payment_status IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_documents_split_payment_status", table_name="documents")
    op.drop_column("documents", "split_payment_status")
