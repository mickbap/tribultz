"""add reports table

Revision ID: 2026_03_31_0009
Revises: 2026_03_31_0008
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "2026_03_31_0009"
down_revision = "2026_03_31_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("report_type", sa.String(length=30), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("report_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="generating"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_reports_storage_key"),
        sa.CheckConstraint(
            "report_type IN ('validation', 'batch')",
            name="reports_report_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('generating', 'ready', 'error')",
            name="reports_status_check",
        ),
    )
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"])
    op.create_index("ix_reports_tenant_status", "reports", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_reports_tenant_status", table_name="reports")
    op.drop_index("ix_reports_tenant_id", table_name="reports")
    op.drop_table("reports")
