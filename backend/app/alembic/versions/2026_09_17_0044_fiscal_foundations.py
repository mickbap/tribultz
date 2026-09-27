"""Versioned fiscal facts, tenant-safe parties and fail-closed evidence retention.

No legacy event backfill: existing Simples rows only receive their policy identity.
DDL is frozen here, independent of future ORM changes.
Revision ID: 2026_09_17_0044
Revises: 2026_09_15_0043
"""

from alembic import op
import sqlalchemy as sa

revision = "2026_09_17_0044"
down_revision = "2026_09_15_0043"
branch_labels = None
depends_on = None

TABLES = (
    "fiscal_parties",
    "fiscal_election_policies",
    "fiscal_elections",
    "fiscal_facts",
    "fiscal_fact_evidence",
)


def upgrade() -> None:
    op.add_column(
        "manifestacoes_eleicao_ibs_cbs",
        sa.Column(
            "regime", sa.String(80), nullable=False, server_default="SIMPLES_NACIONAL"
        ),
    )
    op.add_column(
        "manifestacoes_eleicao_ibs_cbs",
        sa.Column(
            "policy_version",
            sa.String(80),
            nullable=False,
            server_default="SIMPLES_2026_V1",
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "retention_class", sa.String(32), nullable=False, server_default="STANDARD"
        ),
    )
    op.add_column("documents", sa.Column("preservation_reason", sa.String(500)))
    op.create_unique_constraint(
        "uq_documents_tenant_id", "documents", ["tenant_id", "id"]
    )
    op.create_check_constraint(
        "ck_documents_retention_class",
        "documents",
        "retention_class IN ('STANDARD', 'FISCAL_EVIDENCE')",
    )
    op.create_check_constraint(
        "ck_documents_preservation_reason",
        "documents",
        "retention_class <> 'FISCAL_EVIDENCE' OR (preservation_reason IS NOT NULL AND length(trim(preservation_reason)) > 0)",
    )
    op.execute("""
CREATE TABLE fiscal_parties (
	party_type VARCHAR(2) NOT NULL,
	identifier VARCHAR(14) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	tenant_id UUID NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, party_type, identifier),
	CONSTRAINT ck_fiscal_party_identity CHECK ((party_type = 'PF' AND identifier ~ '^[0-9]{11}$') OR (party_type = 'PJ' AND identifier ~ '^[A-Z0-9]{12}[0-9]{2}$')),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE fiscal_election_policies (
	regime VARCHAR(80) NOT NULL,
	version VARCHAR(80) NOT NULL,
	mechanism VARCHAR(40) NOT NULL,
	source VARCHAR(500) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	tenant_id UUID NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, regime, version),
	CONSTRAINT ck_fiscal_policy_mechanism CHECK (mechanism = 'EXPLICIT_EVENTS_V1'),
	CONSTRAINT ck_fiscal_policy_source CHECK (length(trim(regime)) > 0 AND length(trim(version)) > 0 AND length(trim(source)) > 0),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE fiscal_elections (
	party_id UUID NOT NULL,
	policy_id UUID NOT NULL,
	fiscal_year INTEGER,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	tenant_id UUID NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	FOREIGN KEY(tenant_id, party_id) REFERENCES fiscal_parties (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, policy_id) REFERENCES fiscal_election_policies (tenant_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_fiscal_election_year CHECK (fiscal_year IS NULL OR fiscal_year BETWEEN 1 AND 9999),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE TABLE fiscal_facts (
    recorded_transaction VARCHAR(32) DEFAULT pg_current_xact_id()::text NOT NULL,
	lineage_id UUID NOT NULL,
	revision INTEGER NOT NULL,
	supersedes_id UUID,
	kind VARCHAR(40) NOT NULL,
	election_id UUID,
	subject_id UUID,
	object_id UUID,
	relationship_type VARCHAR(40),
	event_at DATE,
	effective_from DATE,
	effective_until DATE,
	cancelled_at DATE,
	source VARCHAR(500) NOT NULL,
	source_kind VARCHAR(32) NOT NULL,
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	tenant_id UUID NOT NULL,
	recorded_at TIMESTAMP WITH TIME ZONE DEFAULT clock_timestamp() NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (tenant_id, id),
	UNIQUE (tenant_id, lineage_id, revision),
	UNIQUE (tenant_id, supersedes_id),
	FOREIGN KEY(tenant_id, supersedes_id) REFERENCES fiscal_facts (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, election_id) REFERENCES fiscal_elections (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, subject_id) REFERENCES fiscal_parties (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, object_id) REFERENCES fiscal_parties (tenant_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_fiscal_fact_kind CHECK (kind IN ('OPTION_REQUESTED','OPTION_DEFERRED','OPTION_EFFECTIVE','OPTION_CANCELLED','PROVEN_MEMBER','PROVEN_NOT_MEMBER','TAX_ASSOCIATE_LIST','ASSOCIATE_LIST_UPDATE','MEMBERSHIP_ADMISSION','CORPORATE_EVIDENCE')),
	CONSTRAINT ck_fiscal_fact_source CHECK (source_kind IN ('PRIVATE_DOCUMENT','OFFICIAL_RECORD','REGULATORY_ARTIFACT') AND length(trim(source)) > 0),
	CONSTRAINT ck_fiscal_fact_revision CHECK (revision >= 1 AND ((revision = 1 AND supersedes_id IS NULL) OR (revision > 1 AND supersedes_id IS NOT NULL))),
	CONSTRAINT ck_fiscal_fact_period CHECK (effective_until IS NULL OR (effective_from IS NOT NULL AND effective_until >= effective_from)),
	CONSTRAINT ck_fiscal_fact_owner CHECK ((kind LIKE 'OPTION_%' AND election_id IS NOT NULL AND subject_id IS NULL AND object_id IS NULL AND relationship_type IS NULL) OR (kind NOT LIKE 'OPTION_%' AND election_id IS NULL AND subject_id IS NOT NULL)),
	CONSTRAINT ck_fiscal_fact_relationship CHECK ((kind IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') AND object_id IS NOT NULL AND subject_id <> object_id AND relationship_type IS NOT NULL AND relationship_type = 'MEMBER_OF' AND effective_from IS NOT NULL) OR (kind NOT IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') AND relationship_type IS NULL)),
	CONSTRAINT ck_fiscal_fact_effective CHECK (kind <> 'OPTION_EFFECTIVE' OR effective_from IS NOT NULL),
	CONSTRAINT ck_fiscal_fact_cancelled CHECK ((kind = 'OPTION_CANCELLED' AND cancelled_at IS NOT NULL AND (event_at IS NULL OR event_at = cancelled_at)) OR (kind <> 'OPTION_CANCELLED' AND cancelled_at IS NULL)),
	FOREIGN KEY(tenant_id) REFERENCES tenants (id) ON DELETE RESTRICT
)
    """)
    op.execute("""
CREATE INDEX ix_fiscal_facts_election ON fiscal_facts (tenant_id, election_id, recorded_at)
    """)
    op.execute("""
CREATE INDEX ix_fiscal_facts_relationship ON fiscal_facts (tenant_id, subject_id, object_id, effective_from)
    """)
    op.execute("""
CREATE TABLE fiscal_fact_evidence (
	tenant_id UUID NOT NULL,
	fact_id UUID NOT NULL,
	document_id UUID NOT NULL,
	evidence_type VARCHAR(40) NOT NULL,
	checksum_sha256 VARCHAR(64) NOT NULL,
	PRIMARY KEY (tenant_id, fact_id, document_id, evidence_type),
	FOREIGN KEY(tenant_id, fact_id) REFERENCES fiscal_facts (tenant_id, id) ON DELETE RESTRICT,
	FOREIGN KEY(tenant_id, document_id) REFERENCES documents (tenant_id, id) ON DELETE RESTRICT,
	CONSTRAINT ck_fiscal_evidence_type CHECK (evidence_type IN ('OPTION_REQUEST','OPTION_DEFERMENT','OPTION_EFFECTIVENESS','OPTION_CANCELLATION','FISCAL_YEAR','TAX_ASSOCIATE_LIST','ADMISSION_DATE','ASSOCIATE_LIST_UPDATE','LEGAL_MEMBERSHIP_CREATION','LEGAL_MEMBERSHIP_END','CORPORATE_COMPLEMENT')),
	CONSTRAINT ck_fiscal_evidence_digest CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$')
)
    """)
    op.execute("""
        CREATE FUNCTION prevent_fiscal_history_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'fiscal history is append-only; record a new revision'; END;
        $$ LANGUAGE plpgsql
    """)
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER fiscal_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION prevent_fiscal_history_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER fiscal_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION prevent_fiscal_history_mutation()"
        )
    op.execute("""
        CREATE FUNCTION validate_fiscal_revision() RETURNS trigger AS $$
        DECLARE previous fiscal_facts%ROWTYPE;
        BEGIN
            NEW.recorded_transaction := pg_current_xact_id()::text;
            IF NEW.supersedes_id IS NOT NULL THEN
                SELECT * INTO previous FROM fiscal_facts
                WHERE tenant_id = NEW.tenant_id AND id = NEW.supersedes_id FOR KEY SHARE;
                IF NOT FOUND OR NEW.lineage_id <> previous.lineage_id
                    OR NEW.revision <> previous.revision + 1
                    OR NEW.recorded_at < previous.recorded_at
                    OR ROW(CASE WHEN NEW.kind IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') THEN 'MEMBERSHIP' ELSE NEW.kind END, NEW.election_id, NEW.subject_id, NEW.object_id, NEW.relationship_type)
                       IS DISTINCT FROM ROW(CASE WHEN previous.kind IN ('PROVEN_MEMBER','PROVEN_NOT_MEMBER') THEN 'MEMBERSHIP' ELSE previous.kind END, previous.election_id, previous.subject_id, previous.object_id, previous.relationship_type)
                THEN RAISE EXCEPTION 'invalid fiscal fact revision'; END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER fiscal_revision BEFORE INSERT ON fiscal_facts FOR EACH ROW EXECUTE FUNCTION validate_fiscal_revision()"
    )
    op.execute("""
        CREATE FUNCTION guard_fiscal_document() RETURNS trigger AS $$
        BEGIN
            IF OLD.retention_class = 'FISCAL_EVIDENCE' THEN
                IF TG_OP = 'DELETE' THEN
                    RAISE EXCEPTION 'fiscal evidence has no authorized purge policy; preserve';
                END IF;
                IF NEW.retention_class <> 'FISCAL_EVIDENCE' THEN
                    RAISE EXCEPTION 'fiscal preservation cannot be removed without a retention policy';
                END IF;
                IF EXISTS (SELECT 1 FROM fiscal_fact_evidence WHERE tenant_id = OLD.tenant_id AND document_id = OLD.id)
                   AND ROW(NEW.tenant_id, NEW.status, NEW.storage_key, NEW.fiscal_metadata->'storage_evidence')
                       IS DISTINCT FROM ROW(OLD.tenant_id, OLD.status, OLD.storage_key, OLD.fiscal_metadata->'storage_evidence')
                THEN RAISE EXCEPTION 'linked fiscal document content is immutable'; END IF;
            END IF;
            IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER fiscal_document_guard BEFORE UPDATE OR DELETE ON documents FOR EACH ROW EXECUTE FUNCTION guard_fiscal_document()"
    )
    op.execute("""
        CREATE FUNCTION validate_fiscal_evidence() RETURNS trigger AS $$
        DECLARE doc documents%ROWTYPE; fact_transaction text;
        BEGIN
            SELECT recorded_transaction INTO fact_transaction FROM fiscal_facts WHERE tenant_id = NEW.tenant_id AND id = NEW.fact_id;
            IF NOT FOUND OR fact_transaction IS DISTINCT FROM pg_current_xact_id()::text THEN
                RAISE EXCEPTION 'evidence must be inserted atomically with its fact revision';
            END IF;
            SELECT * INTO doc FROM documents WHERE tenant_id = NEW.tenant_id AND id = NEW.document_id FOR UPDATE;
            IF NOT FOUND OR doc.status <> 'confirmed'
               OR (doc.fiscal_metadata->'storage_evidence'->>'checksum_sha256') IS DISTINCT FROM NEW.checksum_sha256
               OR (doc.fiscal_metadata->'storage_evidence'->>'storage_key') IS DISTINCT FROM doc.storage_key
               OR doc.storage_key NOT LIKE ('documents/' || doc.tenant_id || '/' || doc.doc_type || '/confirmed/' || doc.id || '/%')
            THEN RAISE EXCEPTION 'evidence requires confirmed pinned document content in the same tenant'; END IF;
            UPDATE documents SET retention_class = 'FISCAL_EVIDENCE',
                preservation_reason = COALESCE(NULLIF(trim(preservation_reason), ''), 'Required for fiscal history and provenance')
                WHERE tenant_id = NEW.tenant_id AND id = NEW.document_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER fiscal_evidence_guard BEFORE INSERT ON fiscal_fact_evidence FOR EACH ROW EXECUTE FUNCTION validate_fiscal_evidence()"
    )
    op.execute("""
        CREATE FUNCTION require_fiscal_evidence() RETURNS trigger AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM fiscal_fact_evidence e WHERE e.tenant_id = NEW.tenant_id AND e.fact_id = NEW.id
                AND CASE NEW.kind
                    WHEN 'OPTION_REQUESTED' THEN e.evidence_type = 'OPTION_REQUEST'
                    WHEN 'OPTION_DEFERRED' THEN e.evidence_type = 'OPTION_DEFERMENT'
                    WHEN 'OPTION_EFFECTIVE' THEN e.evidence_type = 'OPTION_EFFECTIVENESS'
                    WHEN 'OPTION_CANCELLED' THEN e.evidence_type = 'OPTION_CANCELLATION'
                    WHEN 'PROVEN_MEMBER' THEN e.evidence_type IN ('LEGAL_MEMBERSHIP_CREATION', 'CORPORATE_COMPLEMENT')
                    WHEN 'PROVEN_NOT_MEMBER' THEN e.evidence_type IN ('LEGAL_MEMBERSHIP_END', 'CORPORATE_COMPLEMENT')
                    WHEN 'TAX_ASSOCIATE_LIST' THEN e.evidence_type = 'TAX_ASSOCIATE_LIST'
                    WHEN 'ASSOCIATE_LIST_UPDATE' THEN e.evidence_type = 'ASSOCIATE_LIST_UPDATE'
                    WHEN 'MEMBERSHIP_ADMISSION' THEN e.evidence_type = 'ADMISSION_DATE'
                    WHEN 'CORPORATE_EVIDENCE' THEN e.evidence_type = 'CORPORATE_COMPLEMENT'
                    ELSE false END
            ) THEN RAISE EXCEPTION 'fact requires typed supporting evidence; a tax list does not create membership'; END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE CONSTRAINT TRIGGER fiscal_fact_requires_evidence AFTER INSERT ON fiscal_facts DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION require_fiscal_evidence()"
    )


def downgrade() -> None:
    # A schema rollback must never silently discard new history or expose protected
    # documents to the old 365-day purger. Empty foundations are reversible; once
    # used, first arrange an explicitly reviewed preservation/lifecycle plan.
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM fiscal_parties)
               OR EXISTS (SELECT 1 FROM fiscal_election_policies)
               OR EXISTS (SELECT 1 FROM documents WHERE retention_class = 'FISCAL_EVIDENCE')
            THEN RAISE EXCEPTION 'preserve fiscal history before downgrade; rollback refused without data loss'; END IF;
        END $$
    """)
    op.execute("DROP TRIGGER fiscal_document_guard ON documents")
    for table in reversed(TABLES):
        op.drop_table(table)
    for function in (
        "require_fiscal_evidence",
        "validate_fiscal_evidence",
        "guard_fiscal_document",
        "validate_fiscal_revision",
        "prevent_fiscal_history_mutation",
    ):
        op.execute(f"DROP FUNCTION {function}()")
    op.drop_constraint("ck_documents_preservation_reason", "documents")
    op.drop_constraint("ck_documents_retention_class", "documents")
    op.drop_constraint("uq_documents_tenant_id", "documents")
    op.drop_column("documents", "preservation_reason")
    op.drop_column("documents", "retention_class")
    op.drop_column("manifestacoes_eleicao_ibs_cbs", "policy_version")
    op.drop_column("manifestacoes_eleicao_ibs_cbs", "regime")
