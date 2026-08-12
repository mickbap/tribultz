"""Fundações do handoff comercial Rumy→Tribultz→Attio — F1 do Round 4 (PO-2026-07-CRM-001).

Cria as quatro tabelas do domínio de handoff: identidade de pessoa (DEC-5),
vínculo operacional do lead, ledger append-only de eventos e trilha de
transições de estado. Espelha app/models/crm_handoff.py coluna a coluna
(fonte única do schema é o Alembic, #409).

Revision ID: 2026_08_12_0037
Revises: 2026_07_28_0036
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_08_12_0037"
down_revision = "2026_07_28_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crm_person_identities",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email_normalized", sa.String(length=320), nullable=True),
        sa.Column("linkedin_normalized", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "email_normalized IS NOT NULL OR linkedin_normalized IS NOT NULL",
            name="ck_crm_person_identities_has_key",
        ),
    )
    op.create_index(
        "uq_crm_person_identities_tenant_email",
        "crm_person_identities",
        ["tenant_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("email_normalized IS NOT NULL"),
    )
    op.create_index(
        "uq_crm_person_identities_tenant_linkedin",
        "crm_person_identities",
        ["tenant_id", "linkedin_normalized"],
        unique=True,
        postgresql_where=sa.text("linkedin_normalized IS NOT NULL"),
    )

    op.create_table(
        "crm_lead_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(length=32), nullable=False, server_default="rumy"),
        sa.Column("external_lead_id", sa.String(length=128), nullable=False),
        sa.Column(
            "person_identity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_person_identities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "identity_conflict", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "provider_ids", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("attio_person_id", sa.String(length=64), nullable=True),
        sa.Column("attio_company_id", sa.String(length=64), nullable=True),
        sa.Column("attio_deal_id", sa.String(length=64), nullable=True),
        sa.Column("commercial_state", sa.String(length=32), nullable=True),
        sa.Column(
            "ownership_state", sa.String(length=24), nullable=False, server_default="AUTOMATED"
        ),
        sa.Column(
            "automation_state", sa.String(length=32), nullable=False, server_default="ACTIVE"
        ),
        sa.Column("owner_ref", sa.String(length=128), nullable=True),
        sa.Column("handoff_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_human_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppression_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suppression_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_applied_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "tenant_id", "source_system", "external_lead_id", name="uq_crm_lead_links_identity"
        ),
    )
    op.create_index("ix_crm_lead_links_person", "crm_lead_links", ["person_identity_id"])

    op.create_table(
        "crm_lead_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(length=32), nullable=False),
        sa.Column("external_lead_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("provider_event_id", sa.String(length=128), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("adapter_version", sa.String(length=32), nullable=True),
        sa.Column("event_type_raw", sa.String(length=128), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "occurred_at_source", sa.String(length=16), nullable=False, server_default="provider"
        ),
        sa.Column(
            "received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("payload_raw", postgresql.JSONB(), nullable=True),
        sa.Column("payload_normalized", postgresql.JSONB(), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="received"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_result", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_crm_lead_events_idempotency"),
    )
    op.create_index(
        "ix_crm_lead_events_lead",
        "crm_lead_events",
        ["tenant_id", "source_system", "external_lead_id", "occurred_at"],
    )

    op.create_table(
        "crm_state_transitions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "lead_link_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("crm_lead_links.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("axis", sa.String(length=16), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_ref", sa.String(length=128), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_crm_state_transitions_link", "crm_state_transitions", ["lead_link_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_crm_state_transitions_link", table_name="crm_state_transitions")
    op.drop_table("crm_state_transitions")
    op.drop_index("ix_crm_lead_events_lead", table_name="crm_lead_events")
    op.drop_table("crm_lead_events")
    op.drop_index("ix_crm_lead_links_person", table_name="crm_lead_links")
    op.drop_table("crm_lead_links")
    op.drop_index("uq_crm_person_identities_tenant_linkedin", table_name="crm_person_identities")
    op.drop_index("uq_crm_person_identities_tenant_email", table_name="crm_person_identities")
    op.drop_table("crm_person_identities")
