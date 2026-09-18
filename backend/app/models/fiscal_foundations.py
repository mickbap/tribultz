"""Tenant-scoped, append-only facts. No tax treatment or Portal vocabulary."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from app.database import Base


class TenantRecord:
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class FiscalParty(TenantRecord, Base):
    __tablename__ = "fiscal_parties"
    party_type: Mapped[str] = mapped_column(String(2), nullable=False)
    identifier: Mapped[str] = mapped_column(String(14), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "party_type", "identifier"),
        CheckConstraint(
            "(party_type = 'PF' AND identifier ~ '^[0-9]{11}$') OR (party_type = 'PJ' AND identifier ~ '^[A-Z0-9]{12}[0-9]{2}$')",
            name="ck_fiscal_party_identity",
        ),
    )


class FiscalElectionPolicy(TenantRecord, Base):
    __tablename__ = "fiscal_election_policies"
    regime: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[str] = mapped_column(String(80), nullable=False)
    mechanism: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "regime", "version"),
        CheckConstraint(
            "mechanism = 'EXPLICIT_EVENTS_V1'", name="ck_fiscal_policy_mechanism"
        ),
        CheckConstraint(
            "length(trim(regime)) > 0 AND length(trim(version)) > 0 AND length(trim(source)) > 0",
            name="ck_fiscal_policy_source",
        ),
    )


class FiscalElection(TenantRecord, Base):
    __tablename__ = "fiscal_elections"
    party_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "party_id"],
            ["fiscal_parties.tenant_id", "fiscal_parties.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "policy_id"],
            ["fiscal_election_policies.tenant_id", "fiscal_election_policies.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "fiscal_year IS NULL OR fiscal_year BETWEEN 1 AND 9999",
            name="ck_fiscal_election_year",
        ),
    )


class FiscalFact(TenantRecord, Base):
    """A revision is a new row; supersession never deletes the previous evidence."""

    __tablename__ = "fiscal_facts"
    # Internal transaction identity seals the document bundle at commit.
    recorded_transaction: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("pg_current_xact_id()::text")
    )
    lineage_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    election_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    subject_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    object_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    relationship_type: Mapped[str | None] = mapped_column(String(40))
    event_at: Mapped[date | None] = mapped_column(Date)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_until: Mapped[date | None] = mapped_column(Date)
    cancelled_at: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(500), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "lineage_id", "revision"),
        UniqueConstraint("tenant_id", "supersedes_id"),
        ForeignKeyConstraint(
            ["tenant_id", "supersedes_id"],
            ["fiscal_facts.tenant_id", "fiscal_facts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "election_id"],
            ["fiscal_elections.tenant_id", "fiscal_elections.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "subject_id"],
            ["fiscal_parties.tenant_id", "fiscal_parties.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "object_id"],
            ["fiscal_parties.tenant_id", "fiscal_parties.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "kind IN ('OPTION_REQUESTED','OPTION_DEFERRED','OPTION_EFFECTIVE','OPTION_CANCELLED','PROVEN_MEMBER','PROVEN_NOT_MEMBER','TAX_ASSOCIATE_LIST','ASSOCIATE_LIST_UPDATE','MEMBERSHIP_ADMISSION','CORPORATE_EVIDENCE')",
            name="ck_fiscal_fact_kind",
        ),
        CheckConstraint(
            "source_kind IN ('PRIVATE_DOCUMENT','OFFICIAL_RECORD','REGULATORY_ARTIFACT') AND length(trim(source)) > 0",
            name="ck_fiscal_fact_source",
        ),
        CheckConstraint(
            "revision >= 1 AND ((revision = 1 AND supersedes_id IS NULL) OR (revision > 1 AND supersedes_id IS NOT NULL))",
            name="ck_fiscal_fact_revision",
        ),
        CheckConstraint(
            "effective_until IS NULL OR (effective_from IS NOT NULL AND effective_until >= effective_from)",
            name="ck_fiscal_fact_period",
        ),
        CheckConstraint(
            "(kind LIKE 'OPTION_%' AND election_id IS NOT NULL AND subject_id IS NULL AND object_id IS NULL AND relationship_type IS NULL) OR (kind NOT LIKE 'OPTION_%' AND election_id IS NULL AND subject_id IS NOT NULL)",
            name="ck_fiscal_fact_owner",
        ),
        CheckConstraint(
            "(kind IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') AND object_id IS NOT NULL AND subject_id <> object_id AND relationship_type IS NOT NULL AND relationship_type = 'MEMBER_OF' AND effective_from IS NOT NULL) OR (kind NOT IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') AND relationship_type IS NULL)",
            name="ck_fiscal_fact_relationship",
        ),
        CheckConstraint(
            "kind <> 'OPTION_EFFECTIVE' OR effective_from IS NOT NULL",
            name="ck_fiscal_fact_effective",
        ),
        CheckConstraint(
            "(kind = 'OPTION_CANCELLED' AND cancelled_at IS NOT NULL AND (event_at IS NULL OR event_at = cancelled_at)) OR (kind <> 'OPTION_CANCELLED' AND cancelled_at IS NULL)",
            name="ck_fiscal_fact_cancelled",
        ),
        Index(
            "ix_fiscal_facts_relationship",
            "tenant_id",
            "subject_id",
            "object_id",
            "effective_from",
        ),
        Index("ix_fiscal_facts_election", "tenant_id", "election_id", "recorded_at"),
    )


class FiscalFactEvidence(Base):
    """Typed evidence is bound to an immutable fact revision and document digest."""

    __tablename__ = "fiscal_fact_evidence"
    tenant_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    fact_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    document_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    evidence_type: Mapped[str] = mapped_column(String(40), primary_key=True)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "fact_id"],
            ["fiscal_facts.tenant_id", "fiscal_facts.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "document_id"],
            ["documents.tenant_id", "documents.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "evidence_type IN ('OPTION_REQUEST','OPTION_DEFERMENT','OPTION_EFFECTIVENESS','OPTION_CANCELLATION','FISCAL_YEAR','TAX_ASSOCIATE_LIST','ADMISSION_DATE','ASSOCIATE_LIST_UPDATE','LEGAL_MEMBERSHIP_CREATION','LEGAL_MEMBERSHIP_END','CORPORATE_COMPLEMENT')",
            name="ck_fiscal_evidence_type",
        ),
        CheckConstraint(
            "checksum_sha256 ~ '^[0-9a-f]{64}$'", name="ck_fiscal_evidence_digest"
        ),
    )
