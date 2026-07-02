"""add_feedback_support_tables — Alembic vira fonte única do schema (#409)

Estas 4 tabelas (models: feedback.py, support.py) existiam apenas no
database/schema.sql, que era montado no docker-entrypoint-initdb.d do compose
e ficou defasado das migrations — todo ambiente dev criado do zero nascia
quebrado. O schema.sql foi aposentado; esta migration fecha a lacuna.

Idempotente por inspector: em produção as tabelas já existem (criadas pelo
schema.sql original) e a migration vira no-op limpo.

Revision ID: 2026_07_02_0023
Revises: 2026_06_30_0022
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_07_02_0023"
down_revision = "2026_06_30_0022"
branch_labels = None
depends_on = None


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()

    if "feedback" not in existing:
        op.create_table(
            "feedback",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(50), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_feedback_tenant", "feedback", ["tenant_id"])

    if "support_tickets" not in existing:
        op.create_table(
            "support_tickets",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'open'")),
            sa.Column("priority", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
            sa.Column("attachments", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("github_issue_url", sa.String(300), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_support_tickets_tenant", "support_tickets", ["tenant_id"])
        op.create_index("idx_support_tickets_user", "support_tickets", ["user_id"])
        op.create_index("idx_support_tickets_status", "support_tickets", ["status"])

    if "support_messages" not in existing:
        op.create_table(
            "support_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("ticket_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("is_staff", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("idx_support_messages_ticket", "support_messages", ["ticket_id"])

    if "known_errors" not in existing:
        op.create_table(
            "known_errors",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False, server_default=sa.text("'medium'")),
            sa.Column("workaround", sa.Text(), nullable=True),
            sa.Column("github_issue_number", sa.Integer(), nullable=True),
            sa.Column("github_issue_url", sa.String(300), nullable=True),
            sa.Column("affected_versions", sa.String(100), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_index("idx_support_tickets_status", table_name="support_tickets")
    op.drop_index("idx_support_tickets_user", table_name="support_tickets")
    op.drop_index("idx_support_tickets_tenant", table_name="support_tickets")
    op.drop_table("support_tickets")
    op.drop_index("idx_feedback_tenant", table_name="feedback")
    op.drop_table("feedback")
    op.drop_table("known_errors")
