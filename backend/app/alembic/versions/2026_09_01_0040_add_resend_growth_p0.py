"""Resend Growth P0: provenance, suppression e ledger de webhook (#733).

Revision ID: 2026_09_01_0040
Revises: 2026_09_01_0039
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_09_01_0040"
down_revision = "2026_09_01_0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prospect_orgs", sa.Column("marketing_origin", sa.String(120)))
    op.add_column("prospect_orgs", sa.Column("marketing_collected_at", sa.Date()))
    op.add_column("prospect_orgs", sa.Column("marketing_purpose", sa.String(160)))
    op.add_column("prospect_orgs", sa.Column("marketing_legal_basis", sa.String(120)))
    op.add_column("prospect_orgs", sa.Column("marketing_lia_evidence_ref", sa.String(500)))
    op.add_column(
        "prospect_orgs",
        sa.Column(
            "marketing_eligibility",
            sa.String(16),
            nullable=False,
            server_default="INELIGIBLE",
        ),
    )
    op.add_column("prospect_orgs", sa.Column("marketing_eligibility_reason", sa.String(240)))
    op.add_column(
        "prospect_orgs", sa.Column("marketing_eligibility_evaluated_at", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        "ck_prospect_orgs_marketing_eligibility",
        "prospect_orgs",
        "marketing_eligibility IN ('ELIGIBLE', 'INELIGIBLE')",
    )

    op.add_column(
        "prospect_suppressions",
        sa.Column("source", sa.String(32), nullable=False, server_default="tribultz"),
    )
    op.add_column("prospect_suppressions", sa.Column("source_event_id", sa.String(128)))
    op.add_column(
        "prospect_suppressions", sa.Column("occurred_at", sa.DateTime(timezone=True))
    )

    op.create_table(
        "resend_webhook_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("svix_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("email_id", sa.String(128)),
        sa.Column("recipient_email", sa.String(320)),
        sa.Column("payload_raw", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("error", sa.Text()),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("svix_id", name="uq_resend_webhook_events_svix_id"),
    )


def downgrade() -> None:
    op.drop_table("resend_webhook_events")
    op.drop_column("prospect_suppressions", "occurred_at")
    op.drop_column("prospect_suppressions", "source_event_id")
    op.drop_column("prospect_suppressions", "source")
    op.drop_constraint(
        "ck_prospect_orgs_marketing_eligibility", "prospect_orgs", type_="check"
    )
    op.drop_column("prospect_orgs", "marketing_eligibility_evaluated_at")
    op.drop_column("prospect_orgs", "marketing_eligibility_reason")
    op.drop_column("prospect_orgs", "marketing_eligibility")
    op.drop_column("prospect_orgs", "marketing_lia_evidence_ref")
    op.drop_column("prospect_orgs", "marketing_legal_basis")
    op.drop_column("prospect_orgs", "marketing_purpose")
    op.drop_column("prospect_orgs", "marketing_collected_at")
    op.drop_column("prospect_orgs", "marketing_origin")
