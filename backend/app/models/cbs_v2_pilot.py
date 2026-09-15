"""Ledger append-only do piloto restrito das APIs de apuração CBS v2.

O modelo preserva observações externas sem promover o que a RFB devolveu a
resultado fiscal do Tribultz. Não há coluna de MATCH/MISMATCH nem identidade de
transação obrigatória nesta versão.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.database import Base


class CbsV2SyncRun(Base):
    """Solicitação imutável que ancora a linhagem de uma consulta."""

    __tablename__ = "cbs_v2_sync_runs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    callback_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    resource: Mapped[str] = mapped_column(String(16), nullable=False)
    cnpj_base: Mapped[str] = mapped_column(String(8), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("callback_id", name="uq_cbs_v2_sync_runs_callback_id"),
        CheckConstraint(
            "environment IN ('PRODUCAO_RESTRITA', 'BETA')",
            name="ck_cbs_v2_sync_runs_environment",
        ),
        CheckConstraint(
            "resource IN ('DEBITOS', 'CREDITOS')",
            name="ck_cbs_v2_sync_runs_resource",
        ),
        CheckConstraint(
            "cnpj_base ~ '^[0-9]{8}$'", name="ck_cbs_v2_sync_runs_cnpj_base"
        ),
        Index("ix_cbs_v2_sync_runs_tenant_created", "tenant_id", "created_at"),
    )


class CbsV2SyncRunEvent(Base):
    """Evento de estado imutável; transições sempre inserem nova linha."""

    __tablename__ = "cbs_v2_sync_run_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cbs_v2_sync_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cbs_v2_sync_run_events.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    ticket: Mapped[str | None] = mapped_column(String(160), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False)
    signed_url_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transport_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="INDETERMINADO"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "dedupe_key", name="uq_cbs_v2_events_tenant_dedupe"
        ),
        CheckConstraint(
            "source IN ('WEBHOOK', 'STATUS_POLL', 'REQUEST_RESPONSE', 'DOWNLOAD_ARTIFACT')",
            name="ck_cbs_v2_events_source",
        ),
        CheckConstraint(
            "state IN ('REQUEST_ACCEPTED', 'PENDENTE', 'EM_PROCESSAMENTO', "
            "'CONCLUIDA', 'ERRO', 'INDETERMINADO')",
            name="ck_cbs_v2_events_state",
        ),
        CheckConstraint(
            "result IN ('NOT_COMPARABLE', 'INDETERMINADO')",
            name="ck_cbs_v2_events_result",
        ),
        CheckConstraint(
            "transport_status_code IS NULL OR transport_status_code BETWEEN 100 AND 599",
            name="ck_cbs_v2_events_transport_status",
        ),
        Index("ix_cbs_v2_events_run_created", "sync_run_id", "created_at"),
        Index("ix_cbs_v2_events_tenant_ticket", "tenant_id", "ticket"),
    )


class CbsV2ExternalObservation(Base):
    """Observação bruta/parseada, sem upsert e sem inferir identidade."""

    __tablename__ = "cbs_v2_external_observations"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cbs_v2_sync_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sync_run_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cbs_v2_sync_run_events.id", ondelete="RESTRICT"),
        nullable=False,
    )
    previous_observation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("cbs_v2_external_observations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    external_transaction_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    observation_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    resource: Mapped[str] = mapped_column(String(16), nullable=False)
    source_payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    raw_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_content_type: Mapped[str] = mapped_column(String(160), nullable=False)
    sanitized_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unknown_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    schema_status: Mapped[str] = mapped_column(String(24), nullable=False)
    comparability: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="NOT_COMPARABLE"
    )
    determination: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="INDETERMINADO"
    )
    synthetic_fixture: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "sync_run_event_id", name="uq_cbs_v2_observations_sync_run_event"
        ),
        CheckConstraint(
            "observation_version >= 1", name="ck_cbs_v2_observations_version"
        ),
        CheckConstraint(
            "schema_status IN ('KNOWN_SUBSET', 'UNKNOWN_FIELDS', 'INCOMPATIBLE', 'NON_JSON')",
            name="ck_cbs_v2_observations_schema_status",
        ),
        CheckConstraint(
            "comparability = 'NOT_COMPARABLE'",
            name="ck_cbs_v2_observations_not_comparable",
        ),
        CheckConstraint(
            "determination = 'INDETERMINADO'",
            name="ck_cbs_v2_observations_indeterminado",
        ),
        CheckConstraint(
            "external_transaction_id IS NULL",
            name="ck_cbs_v2_observations_no_inferred_identity",
        ),
        CheckConstraint(
            "previous_observation_id IS NULL",
            name="ck_cbs_v2_observations_no_inferred_previous",
        ),
        Index(
            "ix_cbs_v2_observations_tenant_run",
            "tenant_id",
            "sync_run_id",
            "observed_at",
        ),
    )
