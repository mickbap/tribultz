"""Internal tenant-bound foundation API; no HTTP, Portal client or fiscal engine.

Callers own the transaction. Facts and typed document links commit atomically.
Validity is inclusive on both ends; recorded_at is a separate knowledge axis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.documents import Document
from app.models.fiscal_foundations import (
    FiscalElection,
    FiscalElectionPolicy,
    FiscalFact,
    FiscalFactEvidence,
    FiscalParty,
)
from app.services.election_policies import EXPLICIT_MECHANISM, resolve_policy


@dataclass(frozen=True)
class EvidenceLink:
    document_id: UUID
    evidence_type: str


@dataclass(frozen=True)
class HistoricalResult:
    state: str
    reason: str
    fact_ids: tuple[UUID, ...] = ()
    effective_from: date | None = None
    effective_until: date | None = None
    cancelled_at: date | None = None


def _owned(session: Session, model, tenant_id: UUID, record_id: UUID):
    record = session.scalar(
        select(model).where(model.tenant_id == tenant_id, model.id == record_id)
    )
    if record is None:
        raise LookupError("record not found in tenant")
    return record


def create_party(
    session: Session, *, tenant_id: UUID, party_type: str, identifier: str
) -> FiscalParty:
    # No numeric cast: CNPJ identifiers may contain letters.
    import re

    normalized = re.sub(r"[./\-\s]", "", identifier).upper()
    pattern = r"[0-9]{11}" if party_type == "PF" else r"[A-Z0-9]{12}[0-9]{2}"
    if party_type not in {"PF", "PJ"} or not re.fullmatch(pattern, normalized):
        raise ValueError("invalid PF/PJ identifier format")
    party = FiscalParty(
        tenant_id=tenant_id, party_type=party_type, identifier=normalized
    )
    session.add(party)
    session.flush()
    return party


def register_policy(
    session: Session, *, tenant_id: UUID, regime: str, version: str, source: str
) -> FiscalElectionPolicy:
    """Version names/source are internal, never invented Portal status or protocol."""
    if not all(v.strip() for v in (regime, version, source)):
        raise ValueError("regime, version and source are required")
    policy = FiscalElectionPolicy(
        tenant_id=tenant_id,
        regime=regime,
        version=version,
        mechanism=EXPLICIT_MECHANISM,
        source=source,
    )
    session.add(policy)
    session.flush()
    return policy


def create_election(
    session: Session,
    *,
    tenant_id: UUID,
    party_id: UUID,
    policy_id: UUID,
    fiscal_year: int | None = None,
) -> FiscalElection:
    _owned(session, FiscalParty, tenant_id, party_id)
    _owned(session, FiscalElectionPolicy, tenant_id, policy_id)
    election = FiscalElection(
        tenant_id=tenant_id,
        party_id=party_id,
        policy_id=policy_id,
        fiscal_year=fiscal_year,
    )
    session.add(election)
    session.flush()
    return election


def preserve_document(
    session: Session, *, tenant_id: UUID, document_id: UUID, reason: str
) -> Document:
    if not reason.strip():
        raise ValueError("preservation reason required")
    # Serialize with purge before any storage deletion. Purge skips locked rows.
    doc = session.scalar(
        select(Document)
        .where(Document.tenant_id == tenant_id, Document.id == document_id)
        .with_for_update()
    )
    if doc is None:
        raise LookupError("document not found in tenant")
    doc.retention_class = "FISCAL_EVIDENCE"  # type: ignore[assignment]
    doc.preservation_reason = reason  # type: ignore[assignment]
    session.flush()
    return doc


def record_fact(
    session: Session,
    *,
    tenant_id: UUID,
    kind: str,
    source: str,
    source_kind: str,
    evidence: list[EvidenceLink],
    election_id: UUID | None = None,
    subject_id: UUID | None = None,
    object_id: UUID | None = None,
    relationship_type: str | None = None,
    event_at: date | None = None,
    effective_from: date | None = None,
    effective_until: date | None = None,
    cancelled_at: date | None = None,
    supersedes_id: UUID | None = None,
) -> FiscalFact:
    """Record an assertion, not a tax decision. Corrections explicitly replace one lineage.

    A list remains a list. Only an independently asserted, documented membership
    fact participates in historical membership queries.
    """
    required_roles = {
        "OPTION_REQUESTED": {"OPTION_REQUEST"},
        "OPTION_DEFERRED": {"OPTION_DEFERMENT"},
        "OPTION_EFFECTIVE": {"OPTION_EFFECTIVENESS"},
        "OPTION_CANCELLED": {"OPTION_CANCELLATION"},
        "PROVEN_MEMBER": {"LEGAL_MEMBERSHIP_CREATION", "CORPORATE_COMPLEMENT"},
        "PROVEN_NOT_MEMBER": {"LEGAL_MEMBERSHIP_END", "CORPORATE_COMPLEMENT"},
        "TAX_ASSOCIATE_LIST": {"TAX_ASSOCIATE_LIST"},
        "ASSOCIATE_LIST_UPDATE": {"ASSOCIATE_LIST_UPDATE"},
        "MEMBERSHIP_ADMISSION": {"ADMISSION_DATE"},
        "CORPORATE_EVIDENCE": {"CORPORATE_COMPLEMENT"},
    }
    if not evidence or not (
        {e.evidence_type for e in evidence} & required_roles.get(kind, set())
    ):
        raise ValueError("fact requires typed supporting evidence")
    if len({(e.document_id, e.evidence_type) for e in evidence}) != len(evidence):
        raise ValueError("duplicate evidence role in fact revision")
    for model, record_id in (
        (FiscalElection, election_id),
        (FiscalParty, subject_id),
        (FiscalParty, object_id),
    ):
        if record_id is not None:
            _owned(session, model, tenant_id, record_id)
    previous = (
        _owned(session, FiscalFact, tenant_id, supersedes_id) if supersedes_id else None
    )
    previous_kind = previous.kind if previous else None
    membership_kinds = {"PROVEN_MEMBER", "PROVEN_NOT_MEMBER"}
    same_kind = previous_kind == kind or {previous_kind, kind} <= membership_kinds
    if previous and (
        not same_kind
        or (
            previous.election_id,
            previous.subject_id,
            previous.object_id,
            previous.relationship_type,
        )
        != (election_id, subject_id, object_id, relationship_type)
    ):
        raise ValueError("a correction must retain the fact kind and owner")
    documents: list[tuple[EvidenceLink, str]] = []
    # All document locks acquired in stable order; insert/link within caller transaction.
    for link in sorted(evidence, key=lambda e: str(e.document_id)):
        doc = session.scalar(
            select(Document)
            .where(Document.tenant_id == tenant_id, Document.id == link.document_id)
            .with_for_update()
        )
        if doc is None:
            raise LookupError("document not found in tenant")
        metadata = doc.fiscal_metadata or {}
        storage = metadata.get("storage_evidence", {})
        checksum = storage.get("checksum_sha256", "")
        prefix = f"documents/{tenant_id}/{doc.doc_type}/confirmed/{doc.id}/"
        if (
            str(doc.status) != "confirmed"
            or not str(doc.storage_key).startswith(prefix)
            or storage.get("storage_key") != str(doc.storage_key)
            or len(checksum) != 64
        ):
            raise ValueError("evidence requires confirmed pinned document content")
        documents.append((link, checksum))
    fact = FiscalFact(
        tenant_id=tenant_id,
        lineage_id=previous.lineage_id if previous else uuid4(),
        revision=previous.revision + 1 if previous else 1,
        supersedes_id=supersedes_id,
        kind=kind,
        election_id=election_id,
        subject_id=subject_id,
        object_id=object_id,
        relationship_type=relationship_type,
        event_at=event_at,
        effective_from=effective_from,
        effective_until=effective_until,
        cancelled_at=cancelled_at,
        source=source,
        source_kind=source_kind,
    )
    session.add(fact)
    session.flush()
    for link, checksum in documents:
        session.add(
            FiscalFactEvidence(
                tenant_id=tenant_id,
                fact_id=fact.id,
                document_id=link.document_id,
                evidence_type=link.evidence_type,
                checksum_sha256=checksum,
            )
        )
    session.flush()
    return fact


def _snapshot(
    session: Session, *, tenant_id: UUID, known_at: datetime | None, **filters
) -> list[FiscalFact]:
    stmt = select(FiscalFact).where(FiscalFact.tenant_id == tenant_id)
    if known_at is not None:
        if known_at.tzinfo is None or known_at.utcoffset() is None:
            raise ValueError("known_at must include a timezone")
        stmt = stmt.where(FiscalFact.recorded_at <= known_at)
    # With no knowledge cutoff, use the transaction snapshot; application/DB clock
    # skew must never hide a fact that has just been recorded.
    for key, value in filters.items():
        stmt = stmt.where(getattr(FiscalFact, key) == value)
    facts = list(session.scalars(stmt))
    # Select current revisions BEFORE testing validity, so a corrected interval
    # cannot resurrect its superseded predecessor outside the new interval.
    superseded = {f.supersedes_id for f in facts if f.supersedes_id is not None}
    return [f for f in facts if f.id not in superseded]


def was_party_member_at(
    session: Session,
    *,
    tenant_id: UUID,
    party_id: UUID,
    cooperative_id: UUID,
    transaction_date: date,
    known_at: datetime | None = None,
) -> HistoricalResult:
    _owned(session, FiscalParty, tenant_id, party_id)
    _owned(session, FiscalParty, tenant_id, cooperative_id)
    facts = _snapshot(
        session,
        tenant_id=tenant_id,
        known_at=known_at,
        subject_id=party_id,
        object_id=cooperative_id,
        relationship_type="MEMBER_OF",
    )
    active = [
        f
        for f in facts
        if f.effective_from is not None
        and f.effective_from <= transaction_date
        and (f.effective_until is None or transaction_date <= f.effective_until)
    ]
    ids = tuple(sorted((f.id for f in active), key=str))
    kinds = {f.kind for f in active}
    if kinds == {"PROVEN_MEMBER"} or kinds == {"PROVEN_NOT_MEMBER"}:
        return HistoricalResult(
            next(iter(kinds)), "documented assertion within its inclusive interval", ids
        )
    return HistoricalResult(
        "INDETERMINATE",
        "conflicting evidence" if active else "no evidence covering date",
        ids,
    )


def resolve_election(
    session: Session,
    *,
    tenant_id: UUID,
    election_id: UUID,
    as_of: date,
    known_at: datetime | None = None,
) -> HistoricalResult:
    election = _owned(session, FiscalElection, tenant_id, election_id)
    policy = _owned(session, FiscalElectionPolicy, tenant_id, election.policy_id)
    facts = _snapshot(
        session, tenant_id=tenant_id, known_at=known_at, election_id=election_id
    )
    return resolve_policy(
        regime=policy.regime,
        version=policy.version,
        mechanism=policy.mechanism,
        facts=facts,
        as_of=as_of,
    )


def project_explicit_election(
    *, facts: list[FiscalFact], as_of: date
) -> HistoricalResult:
    """No inferred approvals/effectiveness, no tax computation, no automatic reopening."""
    if len({(f.tenant_id, f.election_id) for f in facts}) > 1:
        raise ValueError("mixed election or tenant context")
    active = [f for f in facts if f.event_at is None or f.event_at <= as_of]
    ids = tuple(sorted((f.id for f in active), key=str))
    unknown = HistoricalResult(
        "INDETERMINATE", "missing dates, evidence or conflicting events", ids
    )
    if not active or any(f.event_at is None for f in active):
        return unknown
    by_kind: dict[str, list[FiscalFact]] = {}
    for fact in active:
        by_kind.setdefault(fact.kind, []).append(fact)
    if any(len(v) != 1 for v in by_kind.values()) or "OPTION_REQUESTED" not in by_kind:
        return unknown
    request = by_kind["OPTION_REQUESTED"][0]
    deferred = next(iter(by_kind.get("OPTION_DEFERRED", [])), None)
    effective = next(iter(by_kind.get("OPTION_EFFECTIVE", [])), None)
    cancelled = next(iter(by_kind.get("OPTION_CANCELLED", [])), None)
    assert request.event_at is not None
    if any(f.event_at is not None and f.event_at < request.event_at for f in active):
        return unknown
    if cancelled:
        # Day precision cannot establish 'before' for events on the same day.
        if deferred is not None or effective is not None:
            return unknown
        return HistoricalResult(
            "OPTION_CANCELLED",
            "cancelled pending request; NO_EFFECTIVE_ELECTION",
            ids,
            cancelled_at=cancelled.cancelled_at,
        )
    if effective and not deferred:
        return unknown
    if not deferred:
        return HistoricalResult("OPTION_REQUESTED", "no documented deferment", ids)
    if not effective:
        return HistoricalResult("OPTION_DEFERRED", "no documented effectiveness", ids)
    assert deferred.event_at is not None and effective.event_at is not None
    if effective.event_at < deferred.event_at or effective.effective_from is None:
        return unknown
    if effective.effective_from < deferred.event_at:
        return HistoricalResult(
            "INDETERMINATE",
            "retroactive effectiveness requires an explicit policy",
            ids,
        )
    if as_of < effective.effective_from:
        return HistoricalResult(
            "OPTION_DEFERRED",
            "documented future effectiveness",
            ids,
            effective.effective_from,
            effective.effective_until,
        )
    if effective.effective_until is not None and as_of > effective.effective_until:
        return HistoricalResult(
            "INDETERMINATE",
            "outside documented effectiveness; no automatic continuity",
            ids,
            effective.effective_from,
            effective.effective_until,
        )
    return HistoricalResult(
        "OPTION_EFFECTIVE",
        "documented request, deferment and effectiveness",
        ids,
        effective.effective_from,
        effective.effective_until,
    )
