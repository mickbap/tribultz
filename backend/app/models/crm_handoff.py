"""Fundações do handoff comercial Rumy → Tribultz (Round 4, PO-2026-07-CRM-001).

Quatro tabelas, dois papéis:

- Estado corrente: ``crm_person_identities`` (identidade de pessoa, DEC-5) e
  ``crm_lead_links`` (vínculo operacional lead externo ↔ Tribultz, com os
  eixos ownership/automation).
- Ledger: ``crm_lead_events`` (append-only, dedupe-store de idempotência e fonte
  de auditoria) e ``crm_state_transitions`` (trilha de toda transição de estado).

Identidade lógica de lead: (tenant_id, source_system, external_lead_id) — nunca
um id externo global (Round 4 §11). A proteção contra retomada de automação é
por PESSOA (DEC-5): um novo external_lead_id não é nova permissão de abordagem.

Nada aqui tem efeito comercial externo: nenhum router/task importa estes models
em runtime nesta fatia; consumo real chega em fatias futuras atrás de flags.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class CrmPersonIdentity(Base):
    """Registro determinístico de pessoa (DEC-5) — chaves exatas, nunca fuzzy.

    Uma identidade exige ao menos uma chave (e-mail OU LinkedIn normalizados).
    Matching probabilístico é proibido pela DEC-5; a resolução vive em
    app/services/handoff/identity.py e só usa igualdade exata pós-normalização.
    """

    __tablename__ = "crm_person_identities"
    __table_args__ = (
        CheckConstraint(
            "email_normalized IS NOT NULL OR linkedin_normalized IS NOT NULL",
            name="ck_crm_person_identities_has_key",
        ),
        Index(
            "uq_crm_person_identities_tenant_email",
            "tenant_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("email_normalized IS NOT NULL"),
        ),
        Index(
            "uq_crm_person_identities_tenant_linkedin",
            "tenant_id",
            "linkedin_normalized",
            unique=True,
            postgresql_where=text("linkedin_normalized IS NOT NULL"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    email_normalized = Column(String(320), nullable=True)
    linkedin_normalized = Column(String(255), nullable=True)
    display_name = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmLeadLink(Base):
    """Vínculo operacional corrente de um lead externo (Round 3 §11, Round 4 F1).

    Eixos independentes: commercial_state (espelho do funil), ownership_state
    (quem controla a conversa) e automation_state (permissão de outbound).
    A autoridade destes eixos é este banco. O Attio era o espelho externo e
    foi descomissionado (ROUND 18-A); não há mais espelho.
    """

    __tablename__ = "crm_lead_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "source_system", "external_lead_id", name="uq_crm_lead_links_identity"
        ),
        Index("ix_crm_lead_links_person", "person_identity_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    source_system = Column(String(32), nullable=False, server_default="rumy")
    external_lead_id = Column(String(128), nullable=False)
    person_identity_id = Column(
        UUID(as_uuid=True),
        ForeignKey("crm_person_identities.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Resolução de identidade ambígua (e-mail aponta pessoa A, LinkedIn pessoa B).
    # Fail-safe: conflito bloqueia outbound até curadoria humana; nunca há merge.
    identity_conflict = Column(Boolean, nullable=False, server_default=text("false"))
    provider_ids = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))

    # Colunas históricas do espelho Attio, descomissionado no ROUND 18-A.
    # Preservadas de propósito: são DADO de auditoria, não integração. Nada
    # em produção as escreve; dropá-las é decisão separada, com migration.
    attio_person_id = Column(String(64), nullable=True)
    attio_company_id = Column(String(64), nullable=True)
    attio_deal_id = Column(String(64), nullable=True)

    commercial_state = Column(String(32), nullable=True)
    ownership_state = Column(String(24), nullable=False, server_default="AUTOMATED")
    automation_state = Column(String(32), nullable=False, server_default="ACTIVE")
    owner_ref = Column(String(128), nullable=True)

    handoff_requested_at = Column(DateTime(timezone=True), nullable=True)
    handoff_accepted_at = Column(DateTime(timezone=True), nullable=True)
    first_human_action_at = Column(DateTime(timezone=True), nullable=True)
    suppression_requested_at = Column(DateTime(timezone=True), nullable=True)
    suppression_confirmed_at = Column(DateTime(timezone=True), nullable=True)

    last_applied_event_id = Column(UUID(as_uuid=True), nullable=True)
    last_occurred_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class CrmLeadEvent(Base):
    """Ledger append-only dos eventos recebidos (Round 3 A9, Round 4 F1).

    É simultaneamente o dedupe-store (UNIQUE em idempotency_key) e a fonte de
    auditoria/reconstrução. Linhas nunca são apagadas; reprocessos incrementam
    ``attempts`` e o desfecho fica em ``status``/``processing_result``.
    """

    __tablename__ = "crm_lead_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_crm_lead_events_idempotency"),
        Index(
            "ix_crm_lead_events_lead",
            "tenant_id",
            "source_system",
            "external_lead_id",
            "occurred_at",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    source_system = Column(String(32), nullable=False)
    external_lead_id = Column(String(128), nullable=False)
    idempotency_key = Column(String(128), nullable=False)
    provider_event_id = Column(String(128), nullable=True)
    schema_version = Column(String(16), nullable=False)
    adapter_version = Column(String(32), nullable=True)
    event_type_raw = Column(String(128), nullable=True)
    event_type = Column(String(64), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    # 'provider' = veio do produtor; 'received' = aproximado pelo recebimento
    occurred_at_source = Column(String(16), nullable=False, server_default="provider")
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payload_raw = Column(JSONB, nullable=True)
    payload_normalized = Column(JSONB, nullable=True)
    payload_hash = Column(String(64), nullable=False)
    # received|applied|duplicate|quarantined|superseded|unmapped|failed
    status = Column(String(16), nullable=False, server_default="received")
    attempts = Column(Integer, nullable=False, server_default="1")
    error = Column(Text, nullable=True)
    applied_at = Column(DateTime(timezone=True), nullable=True)
    processing_result = Column(JSONB, nullable=True)


class CrmStateTransition(Base):
    """Trilha append-only de transições de estado (auditoria do Round 4 F3).

    axis: 'ownership' | 'automation' | 'activity' — cada mudança registra quem
    (actor_type/actor_ref), de onde, para onde, por quê e por qual evento.
    """

    __tablename__ = "crm_state_transitions"
    __table_args__ = (Index("ix_crm_state_transitions_link", "lead_link_id", "created_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    lead_link_id = Column(
        UUID(as_uuid=True), ForeignKey("crm_lead_links.id", ondelete="CASCADE"), nullable=False
    )
    axis = Column(String(16), nullable=False)
    from_state = Column(String(32), nullable=True)
    to_state = Column(String(32), nullable=False)
    # HUMAN | SYSTEM | PROVIDER_EVENT — distinção bot×humano é invariante (E-3)
    actor_type = Column(String(16), nullable=False)
    actor_ref = Column(String(128), nullable=True)
    reason = Column(Text, nullable=True)
    event_id = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
