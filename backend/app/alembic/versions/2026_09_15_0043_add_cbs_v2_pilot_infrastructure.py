"""Infraestrutura append-only do piloto CBS v2 (desligada por padrão).

Revision ID: 2026_09_15_0043
Revises: 2026_09_09_0042
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_09_15_0043"
down_revision = "2026_09_09_0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cbs_v2_sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("callback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("resource", sa.String(16), nullable=False),
        sa.Column("cnpj_base", sa.String(8), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("environment IN ('PRODUCAO_RESTRITA', 'BETA')", name="ck_cbs_v2_sync_runs_environment"),
        sa.CheckConstraint("resource IN ('DEBITOS', 'CREDITOS')", name="ck_cbs_v2_sync_runs_resource"),
        sa.CheckConstraint("cnpj_base ~ '^[0-9]{8}$'", name="ck_cbs_v2_sync_runs_cnpj_base"),
        sa.UniqueConstraint("callback_id", name="uq_cbs_v2_sync_runs_callback_id"),
    )
    op.create_index("ix_cbs_v2_sync_runs_tenant_created", "cbs_v2_sync_runs", ["tenant_id", "created_at"])

    op.create_table(
        "cbs_v2_sync_run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cbs_v2_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cbs_v2_sync_run_events.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("ticket", sa.String(160), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_fingerprint", sa.String(64), nullable=False),
        sa.Column("artifact_fingerprint", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(64), nullable=False),
        sa.Column("signed_url_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transport_status_code", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(24), server_default="INDETERMINADO", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source IN ('WEBHOOK', 'STATUS_POLL', 'REQUEST_RESPONSE', 'DOWNLOAD_ARTIFACT')", name="ck_cbs_v2_events_source"),
        sa.CheckConstraint("state IN ('REQUEST_ACCEPTED', 'PENDENTE', 'EM_PROCESSAMENTO', 'CONCLUIDA', 'ERRO', 'INDETERMINADO')", name="ck_cbs_v2_events_state"),
        sa.CheckConstraint("result IN ('NOT_COMPARABLE', 'INDETERMINADO')", name="ck_cbs_v2_events_result"),
        sa.CheckConstraint("transport_status_code IS NULL OR transport_status_code BETWEEN 100 AND 599", name="ck_cbs_v2_events_transport_status"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_cbs_v2_events_tenant_dedupe"),
    )
    op.create_index("ix_cbs_v2_events_run_created", "cbs_v2_sync_run_events", ["sync_run_id", "created_at"])
    op.create_index("ix_cbs_v2_events_tenant_ticket", "cbs_v2_sync_run_events", ["tenant_id", "ticket"])

    op.create_table(
        "cbs_v2_external_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cbs_v2_sync_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sync_run_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cbs_v2_sync_run_events.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("previous_observation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("cbs_v2_external_observations.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("external_transaction_id", sa.String(200), nullable=True),
        sa.Column("observation_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_version", sa.String(64), nullable=False),
        sa.Column("parser_version", sa.String(64), nullable=False),
        sa.Column("resource", sa.String(16), nullable=False),
        sa.Column("source_payload_fingerprint", sa.String(64), nullable=False),
        sa.Column("raw_bucket", sa.String(128), nullable=False),
        sa.Column("raw_object_key", sa.Text(), nullable=False),
        sa.Column("raw_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("raw_content_type", sa.String(160), nullable=False),
        sa.Column("sanitized_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unknown_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("schema_status", sa.String(24), nullable=False),
        sa.Column("comparability", sa.String(24), nullable=False, server_default="NOT_COMPARABLE"),
        sa.Column("determination", sa.String(24), nullable=False, server_default="INDETERMINADO"),
        sa.Column("synthetic_fixture", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("observation_version >= 1", name="ck_cbs_v2_observations_version"),
        sa.CheckConstraint("schema_status IN ('KNOWN_SUBSET', 'UNKNOWN_FIELDS', 'INCOMPATIBLE', 'NON_JSON')", name="ck_cbs_v2_observations_schema_status"),
        sa.CheckConstraint("comparability = 'NOT_COMPARABLE'", name="ck_cbs_v2_observations_not_comparable"),
        sa.CheckConstraint("determination = 'INDETERMINADO'", name="ck_cbs_v2_observations_indeterminado"),
        sa.CheckConstraint("external_transaction_id IS NULL", name="ck_cbs_v2_observations_no_inferred_identity"),
        sa.CheckConstraint("previous_observation_id IS NULL", name="ck_cbs_v2_observations_no_inferred_previous"),
        sa.UniqueConstraint("sync_run_event_id", name="uq_cbs_v2_observations_sync_run_event"),
    )
    op.create_index("ix_cbs_v2_observations_tenant_run", "cbs_v2_external_observations", ["tenant_id", "sync_run_id", "observed_at"])

    # O banco, não apenas a convenção do serviço, garante append-only.
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_cbs_v2_ledger_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'CBS v2 pilot ledger is append-only';
        END;
        $$ LANGUAGE plpgsql
    """)
    for table in (
        "cbs_v2_sync_runs",
        "cbs_v2_sync_run_events",
        "cbs_v2_external_observations",
    ):
        op.execute(f"""
            CREATE TRIGGER trg_{table}_append_only
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION prevent_cbs_v2_ledger_mutation()
        """)


def downgrade() -> None:
    for table in (
        "cbs_v2_external_observations",
        "cbs_v2_sync_run_events",
        "cbs_v2_sync_runs",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.execute("DROP FUNCTION IF EXISTS prevent_cbs_v2_ledger_mutation()")
    op.drop_index("ix_cbs_v2_observations_tenant_run", table_name="cbs_v2_external_observations")
    op.drop_table("cbs_v2_external_observations")
    op.drop_index("ix_cbs_v2_events_tenant_ticket", table_name="cbs_v2_sync_run_events")
    op.drop_index("ix_cbs_v2_events_run_created", table_name="cbs_v2_sync_run_events")
    op.drop_table("cbs_v2_sync_run_events")
    op.drop_index("ix_cbs_v2_sync_runs_tenant_created", table_name="cbs_v2_sync_runs")
    op.drop_table("cbs_v2_sync_runs")
