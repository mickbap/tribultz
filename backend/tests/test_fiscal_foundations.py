"""Real PostgreSQL integrity, historical semantics and retention regression."""

from datetime import date, datetime, timedelta, timezone
import os
from uuid import UUID, uuid4
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError, DBAPIError
from sqlalchemy.orm import Session

from app.models.auth import Tenant, User
from app.models.documents import Document
from app.models.fiscal_foundations import FiscalElection, FiscalFact, FiscalFactEvidence
from app.services.fiscal_foundations import (
    EvidenceLink,
    create_election,
    create_party,
    preserve_document,
    record_fact,
    register_policy,
    resolve_election,
    was_party_member_at,
)


@pytest.fixture
def db():
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        tx = conn.begin()
        session = Session(bind=conn)
        yield session
        session.close()
        tx.rollback()
    engine.dispose()


@pytest.fixture
def world(db):
    return make_world(db)


def make_world(db):
    tenant = Tenant(name="Foundation test", slug=f"foundation-{uuid4()}")
    db.add(tenant)
    db.flush()
    user = User(
        tenant_id=UUID(str(tenant.id)),
        email=f"{uuid4()}@example.test",
        full_name="Test",
        password_hash="test",
        role="admin",
    )
    db.add(user)
    db.flush()
    a = create_party(
        db, tenant_id=UUID(str(tenant.id)), party_type="PF", identifier="123.456.789-01"
    )
    b = create_party(
        db,
        tenant_id=UUID(str(tenant.id)),
        party_type="PJ",
        identifier="AB.CDE.FGH/0001-23",
    )
    policy = register_policy(
        db,
        tenant_id=UUID(str(tenant.id)),
        regime="TEST_REGIME",
        version="v1",
        source="synthetic policy",
    )
    election = create_election(
        db,
        tenant_id=UUID(str(tenant.id)),
        party_id=b.id,
        policy_id=policy.id,
        fiscal_year=2027,
    )
    return tenant, user, a, b, election


def document(db, world, *, age=0, confirmed=True):
    tenant, user, *_ = world
    did = uuid4()
    key = f"documents/{tenant.id}/other/confirmed/{did}/" + "a" * 64
    doc = Document(
        id=did,
        tenant_id=UUID(str(tenant.id)),
        user_id=user.id,
        doc_type="other",
        storage_key=key,
        status="confirmed" if confirmed else "pending_upload",
        created_at=datetime.now(timezone.utc) - timedelta(days=age),
        fiscal_metadata={
            "storage_evidence": {"checksum_sha256": "a" * 64, "storage_key": key}
        },
    )
    db.add(doc)
    db.flush()
    return doc


ROLE = {
    "OPTION_REQUESTED": "OPTION_REQUEST",
    "OPTION_DEFERRED": "OPTION_DEFERMENT",
    "OPTION_EFFECTIVE": "OPTION_EFFECTIVENESS",
    "OPTION_CANCELLED": "OPTION_CANCELLATION",
    "PROVEN_MEMBER": "LEGAL_MEMBERSHIP_CREATION",
    "PROVEN_NOT_MEMBER": "LEGAL_MEMBERSHIP_END",
    "TAX_ASSOCIATE_LIST": "TAX_ASSOCIATE_LIST",
    "ASSOCIATE_LIST_UPDATE": "ASSOCIATE_LIST_UPDATE",
    "MEMBERSHIP_ADMISSION": "ADMISSION_DATE",
    "CORPORATE_EVIDENCE": "CORPORATE_COMPLEMENT",
}


def fact(db, world, kind, *, doc=None, role=None, **kwargs):
    tenant, _, a, b, election = world
    doc = doc or document(db, world)
    if kind.startswith("OPTION_"):
        kwargs.setdefault("election_id", election.id)
    else:
        kwargs.setdefault("subject_id", a.id)
        kwargs.setdefault("object_id", b.id)
        if kind.startswith("PROVEN_"):
            kwargs.setdefault("relationship_type", "MEMBER_OF")
    return record_fact(
        db,
        tenant_id=UUID(str(tenant.id)),
        kind=kind,
        source="synthetic private record",
        source_kind="PRIVATE_DOCUMENT",
        evidence=[EvidenceLink(UUID(str(doc.id)), role or ROLE[kind])],
        **kwargs,
    )


def resolve(db, world, day=date(2027, 1, 1), **kwargs):
    return resolve_election(
        db, tenant_id=world[0].id, election_id=world[4].id, as_of=day, **kwargs
    )


def member(db, world, day=date(2027, 1, 1), **kwargs):
    return was_party_member_at(
        db,
        tenant_id=world[0].id,
        party_id=world[2].id,
        cooperative_id=world[3].id,
        transaction_date=day,
        **kwargs,
    )


def requested(db, world):
    return fact(db, world, "OPTION_REQUESTED", event_at=date(2026, 9, 1))


def deferred(db, world):
    return fact(db, world, "OPTION_DEFERRED", event_at=date(2026, 10, 1))


def effective(db, world):
    return fact(
        db,
        world,
        "OPTION_EFFECTIVE",
        event_at=date(2026, 10, 2),
        effective_from=date(2027, 1, 1),
        effective_until=date(2027, 12, 31),
    )


def test_no_automatic_deferment_or_effectiveness(db, world):
    assert resolve(db, world).state == "INDETERMINATE"
    requested(db, world)
    assert resolve(db, world, date(2030, 1, 1)).state == "OPTION_REQUESTED"
    deferred(db, world)
    assert resolve(db, world, date(2030, 1, 1)).state == "OPTION_DEFERRED"
    effective(db, world)
    assert resolve(db, world, date(2026, 12, 31)).state == "OPTION_DEFERRED"
    assert resolve(db, world).state == "OPTION_EFFECTIVE"
    assert resolve(db, world, date(2027, 12, 31)).state == "OPTION_EFFECTIVE"
    assert resolve(db, world, date(2028, 1, 1)).state == "INDETERMINATE"
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_pending_cancellation_never_becomes_effective(db, world):
    requested(db, world)
    fact(
        db,
        world,
        "OPTION_CANCELLED",
        event_at=date(2026, 9, 20),
        cancelled_at=date(2026, 9, 20),
    )
    assert resolve(db, world).state == "OPTION_CANCELLED"
    assert resolve(db, world).cancelled_at == date(2026, 9, 20)
    deferred(db, world)
    effective(db, world)
    assert resolve(db, world).state == "INDETERMINATE"


@pytest.mark.parametrize("missing", ["request", "deferment"])
def test_effectiveness_requires_its_own_full_chain(db, world, missing):
    if missing != "request":
        requested(db, world)
    if missing != "deferment":
        deferred(db, world)
    effective(db, world)
    assert resolve(db, world).state == "INDETERMINATE"


def test_unknown_event_date_and_conflicting_requests_remain_indeterminate(db, world):
    fact(db, world, "OPTION_REQUESTED")
    assert resolve(db, world).state == "INDETERMINATE"
    requested(db, world)
    assert resolve(db, world).state == "INDETERMINATE"


def test_current_list_does_not_prove_historical_membership(db, world):
    assert member(db, world).state == "INDETERMINATE"
    fact(db, world, "TAX_ASSOCIATE_LIST", event_at=date(2027, 1, 1))
    fact(db, world, "MEMBERSHIP_ADMISSION", event_at=date(2026, 12, 1))
    assert member(db, world).state == "INDETERMINATE"
    fact(
        db,
        world,
        "PROVEN_MEMBER",
        effective_from=date(2027, 2, 1),
        effective_until=date(2027, 3, 1),
    )
    assert member(db, world).state == "INDETERMINATE"
    assert member(db, world, date(2027, 2, 1)).state == "PROVEN_MEMBER"
    assert member(db, world, date(2027, 3, 1)).state == "PROVEN_MEMBER"
    assert member(db, world, date(2027, 3, 2)).state == "INDETERMINATE"


def test_explicit_negative_and_conflict(db, world):
    fact(db, world, "PROVEN_NOT_MEMBER", effective_from=date(2026, 1, 1))
    assert member(db, world).state == "PROVEN_NOT_MEMBER"
    fact(db, world, "PROVEN_MEMBER", effective_from=date(2027, 1, 1))
    assert member(db, world).state == "INDETERMINATE"
    assert member(db, world).reason == "conflicting evidence"


def test_revision_preserves_previous_proofs_and_historical_knowledge(db, world):
    first = fact(db, world, "PROVEN_MEMBER", effective_from=date(2026, 1, 1))
    known_at = first.recorded_at
    second = fact(
        db,
        world,
        "PROVEN_MEMBER",
        effective_from=date(2027, 2, 1),
        supersedes_id=first.id,
    )
    assert second.revision == 2 and second.lineage_id == first.lineage_id
    assert member(db, world).state == "INDETERMINATE"
    assert member(db, world, known_at=known_at).state == "PROVEN_MEMBER"
    assert db.scalar(select(FiscalFact).where(FiscalFact.id == first.id)) is not None
    assert (
        len(
            list(
                db.scalars(
                    select(FiscalFactEvidence).where(
                        FiscalFactEvidence.tenant_id == world[0].id
                    )
                )
            )
        )
        == 2
    )
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_list_cannot_be_sole_evidence_of_membership(db, world):
    with pytest.raises(ValueError, match="typed supporting evidence"):
        with db.begin_nested():
            fact(
                db,
                world,
                "PROVEN_MEMBER",
                effective_from=date(2026, 1, 1),
                role="TAX_ASSOCIATE_LIST",
            )
            db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_no_unconfirmed_document_can_be_evidence(db, world):
    with pytest.raises(ValueError, match="confirmed pinned"):
        fact(db, world, "OPTION_REQUESTED", doc=document(db, world, confirmed=False))


def test_cross_tenant_references_rejected_by_service_and_database(db, world):
    other = Tenant(name="Other", slug=str(uuid4()))
    db.add(other)
    db.flush()
    with pytest.raises(LookupError):
        resolve_election(
            db,
            tenant_id=UUID(str(other.id)),
            election_id=world[4].id,
            as_of=date(2027, 1, 1),
        )
    with pytest.raises(LookupError):
        was_party_member_at(
            db,
            tenant_id=UUID(str(other.id)),
            party_id=world[2].id,
            cooperative_id=world[3].id,
            transaction_date=date(2027, 1, 1),
        )
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                FiscalElection(
                    tenant_id=UUID(str(other.id)),
                    party_id=world[3].id,
                    policy_id=world[4].policy_id,
                )
            )
            db.flush()
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            db.add(
                FiscalFact(
                    tenant_id=UUID(str(other.id)),
                    lineage_id=uuid4(),
                    revision=1,
                    kind="PROVEN_MEMBER",
                    subject_id=world[2].id,
                    object_id=world[3].id,
                    relationship_type="MEMBER_OF",
                    effective_from=date(2026, 1, 1),
                    source="test",
                    source_kind="PRIVATE_DOCUMENT",
                )
            )
            db.flush()
    with pytest.raises(LookupError):
        preserve_document(
            db,
            tenant_id=UUID(str(other.id)),
            document_id=UUID(str(document(db, world).id)),
            reason="test",
        )


def test_facts_and_links_cannot_be_overwritten_or_deleted(db, world):
    f = requested(db, world)
    for sql in (
        "UPDATE fiscal_facts SET source = 'changed' WHERE id = :id",
        "DELETE FROM fiscal_facts WHERE id = :id",
        "DELETE FROM fiscal_fact_evidence WHERE fact_id = :id",
    ):
        with pytest.raises(DBAPIError, match="append-only"):
            with db.begin_nested():
                db.execute(text(sql), {"id": f.id})


def test_document_guard_blocks_delete_reclassification_and_overwrite(db, world):
    doc = document(db, world, age=400)
    fact(db, world, "OPTION_REQUESTED", doc=doc)
    for sql in (
        "DELETE FROM documents WHERE id = :id",
        "UPDATE documents SET retention_class = 'STANDARD' WHERE id = :id",
        "UPDATE documents SET storage_key = 'changed' WHERE id = :id",
    ):
        with pytest.raises(DBAPIError):
            with db.begin_nested():
                db.execute(text(sql), {"id": doc.id})


def test_purger_preserves_marked_and_linked_evidence(db, world, monkeypatch):
    from app.tasks import task_j_retention

    ordinary = document(db, world, age=400)
    marked = document(db, world, age=400)
    linked = document(db, world, age=400)
    preserve_document(
        db,
        tenant_id=world[0].id,
        document_id=UUID(str(marked.id)),
        reason="pending retention policy",
    )
    fact(db, world, "OPTION_REQUESTED", doc=linked)
    monkeypatch.setattr(task_j_retention, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)
    with patch("app.tasks.task_j_retention.delete_object") as delete:
        task_j_retention.purge_expired_documents()
    deleted_keys = [c.args[0] for c in delete.call_args_list]
    assert ordinary.storage_key in deleted_keys
    assert (
        marked.storage_key not in deleted_keys
        and linked.storage_key not in deleted_keys
    )
    db.expire_all()
    assert (
        db.get(Document, marked.id) is not None
        and db.get(Document, linked.id) is not None
    )


def test_policy_is_versioned_and_immutable(db, world):
    policy2 = register_policy(
        db,
        tenant_id=world[0].id,
        regime="TEST_REGIME",
        version="v2",
        source="new policy",
    )
    assert policy2.id != world[4].policy_id
    with pytest.raises(DBAPIError, match="append-only"):
        with db.begin_nested():
            db.execute(
                text(
                    "UPDATE fiscal_election_policies SET version='changed' WHERE id=:id"
                ),
                {"id": policy2.id},
            )


def test_correction_can_reverse_a_membership_assertion_without_erasing_history(
    db, world
):
    first = fact(db, world, "PROVEN_MEMBER", effective_from=date(2026, 1, 1))
    fact(
        db,
        world,
        "PROVEN_NOT_MEMBER",
        effective_from=date(2026, 1, 1),
        supersedes_id=first.id,
    )
    assert member(db, world).state == "PROVEN_NOT_MEMBER"
    assert db.get(FiscalFact, first.id) is not None
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_database_rejects_missing_evidence_even_without_service(db, world):
    with pytest.raises(DBAPIError, match="typed supporting evidence"):
        with db.begin_nested():
            db.add(
                FiscalFact(
                    tenant_id=world[0].id,
                    lineage_id=uuid4(),
                    revision=1,
                    kind="OPTION_REQUESTED",
                    election_id=world[4].id,
                    source="test",
                    source_kind="OFFICIAL_RECORD",
                )
            )
            db.flush()
            db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_database_rejects_cross_tenant_document_link(db, world):
    other = Tenant(name="Other", slug=str(uuid4()))
    db.add(other)
    db.flush()
    f = requested(db, world)
    with pytest.raises(DBAPIError):
        with db.begin_nested():
            db.add(
                FiscalFactEvidence(
                    tenant_id=other.id,
                    fact_id=f.id,
                    document_id=document(db, world).id,
                    evidence_type="OPTION_REQUEST",
                    checksum_sha256="a" * 64,
                )
            )
            db.flush()


def test_unknown_policy_has_no_fallback_and_known_at_requires_timezone(db, world):
    from app.services.election_policies import resolve_policy

    with pytest.raises(ValueError, match="unknown"):
        resolve_policy(regime="TEST", version="v1", mechanism="GUESS")
    with pytest.raises(ValueError, match="timezone"):
        member(db, world, known_at=datetime(2027, 1, 1))


def test_events_may_arrive_out_of_order_without_changing_chronology(db, world):
    effective(db, world)
    assert resolve(db, world).state == "INDETERMINATE"
    deferred(db, world)
    requested(db, world)
    assert resolve(db, world).state == "OPTION_EFFECTIVE"


def test_one_document_can_support_separate_evidence_roles(db, world):
    doc = document(db, world)
    f = record_fact(
        db,
        tenant_id=world[0].id,
        kind="OPTION_REQUESTED",
        election_id=world[4].id,
        source="test",
        source_kind="OFFICIAL_RECORD",
        evidence=[
            EvidenceLink(UUID(str(doc.id)), "OPTION_REQUEST"),
            EvidenceLink(UUID(str(doc.id)), "FISCAL_YEAR"),
        ],
    )
    assert (
        len(
            list(
                db.scalars(
                    select(FiscalFactEvidence).where(FiscalFactEvidence.fact_id == f.id)
                )
            )
        )
        == 2
    )
    db.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_revision_cannot_switch_tenants_or_parties_or_fork(db, world):
    first = fact(db, world, "PROVEN_MEMBER", effective_from=date(2026, 1, 1))
    third = create_party(
        db, tenant_id=world[0].id, party_type="PF", identifier="98765432100"
    )
    with pytest.raises(ValueError, match="owner"):
        fact(
            db,
            world,
            "PROVEN_MEMBER",
            subject_id=third.id,
            effective_from=date(2026, 1, 1),
            supersedes_id=first.id,
        )
    fact(
        db,
        world,
        "PROVEN_MEMBER",
        effective_from=date(2026, 2, 1),
        supersedes_id=first.id,
    )
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            fact(
                db,
                world,
                "PROVEN_MEMBER",
                effective_from=date(2026, 3, 1),
                supersedes_id=first.id,
            )


def test_non_simples_policy_cannot_select_legacy_automatic_semantics(db, world):
    from app.services.election_policies import resolve_policy, SIMPLES_VERSION

    with pytest.raises(ValueError, match="unknown legacy"):
        resolve_policy(
            regime="TEST", version=SIMPLES_VERSION, mechanism=SIMPLES_VERSION
        )
