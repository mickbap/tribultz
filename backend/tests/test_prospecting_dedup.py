"""Deduplicação por domínio de e-mail nominal (PO-2026-07-SALES-001, Fase 1) — DB-backed."""

import os
import uuid
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.prospect_org import ProspectOrg
from app.services.prospecting.dedup import apply_dedup


def _status(org: ProspectOrg) -> str:
    return cast(str, org.dedup_status)


def _merged_into(org: ProspectOrg):
    return cast("uuid.UUID | None", org.merged_into_id)


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def session():
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


def _make_org(
    session,
    *,
    email_domain: str | None,
    email_domain_category: str = "dominio_nominal",
    qtd_estabelecimentos: int = 1,
    capital_social: Decimal = Decimal("0"),
    cnpj_basico: str | None = None,
) -> ProspectOrg:
    cnpj_basico = cnpj_basico or uuid.uuid4().hex[:8]
    org = ProspectOrg(
        cnpj_basico=cnpj_basico,
        cnpj_matriz=f"{cnpj_basico}000191",
        razao_social=f"Empresa {cnpj_basico}",
        porte="05",
        capital_social=capital_social,
        situacao_cadastral="02",
        qtd_estabelecimentos=qtd_estabelecimentos,
        uf="RS",
        email_domain=email_domain,
        email_domain_category=email_domain_category,
        cnae_principal="6920601",
        source_dump_reference="test",
    )
    session.add(org)
    session.flush()
    return org


class TestMergesNominalDomainGroups:
    def test_merges_two_orgs_sharing_nominal_domain(self, session):
        primary = _make_org(session, email_domain="silva.com.br", qtd_estabelecimentos=3)
        other = _make_org(session, email_domain="silva.com.br", qtd_estabelecimentos=1)

        apply_dedup(session)
        session.refresh(primary)
        session.refresh(other)

        assert _status(primary) == "primary"
        assert _status(other) == "merged"
        assert _merged_into(other) == primary.id

    def test_does_not_merge_free_email_domain(self, session):
        a = _make_org(session, email_domain="gmail.com", email_domain_category="gratuito")
        b = _make_org(session, email_domain="gmail.com", email_domain_category="gratuito")

        apply_dedup(session)
        session.refresh(a)
        session.refresh(b)

        assert _status(a) == "unique"
        assert _status(b) == "unique"

    def test_group_larger_than_max_size_is_not_merged(self, session):
        orgs = [_make_org(session, email_domain="plataforma.com.br") for _ in range(6)]

        apply_dedup(session, max_group_size=5)

        for org in orgs:
            session.refresh(org)
            assert _status(org) == "unique"

    def test_unrelated_org_with_unique_domain_stays_unique(self, session):
        solo = _make_org(session, email_domain="unico.com.br")

        apply_dedup(session)
        session.refresh(solo)

        assert _status(solo) == "unique"


class TestTieBreak:
    def test_prefers_more_estabelecimentos(self, session):
        weaker = _make_org(session, email_domain="empate.com.br", qtd_estabelecimentos=1, capital_social=Decimal("100"))
        stronger = _make_org(session, email_domain="empate.com.br", qtd_estabelecimentos=5, capital_social=Decimal("1"))

        apply_dedup(session)
        session.refresh(weaker)
        session.refresh(stronger)

        assert _status(stronger) == "primary"
        assert _merged_into(weaker) == stronger.id

    def test_falls_back_to_capital_social_when_same_estabelecimentos(self, session):
        poorer = _make_org(session, email_domain="empate2.com.br", qtd_estabelecimentos=2, capital_social=Decimal("100"))
        richer = _make_org(session, email_domain="empate2.com.br", qtd_estabelecimentos=2, capital_social=Decimal("999999"))

        apply_dedup(session)
        session.refresh(poorer)
        session.refresh(richer)

        assert _status(richer) == "primary"
        assert _merged_into(poorer) == richer.id

    def test_falls_back_to_lowest_cnpj_basico_as_final_tiebreak(self, session):
        second = _make_org(
            session, email_domain="empate3.com.br", qtd_estabelecimentos=1,
            capital_social=Decimal("0"), cnpj_basico="90000002",
        )
        first = _make_org(
            session, email_domain="empate3.com.br", qtd_estabelecimentos=1,
            capital_social=Decimal("0"), cnpj_basico="90000001",
        )

        apply_dedup(session)
        session.refresh(first)
        session.refresh(second)

        assert _status(first) == "primary"
        assert _merged_into(second) == first.id


class TestIdempotency:
    def test_rerunning_produces_the_same_result(self, session):
        primary = _make_org(session, email_domain="reprocessa.com.br", qtd_estabelecimentos=3)
        other = _make_org(session, email_domain="reprocessa.com.br", qtd_estabelecimentos=1)

        first_run = apply_dedup(session)
        second_run = apply_dedup(session)

        session.refresh(primary)
        session.refresh(other)
        assert first_run == second_run
        assert _status(primary) == "primary"
        assert _status(other) == "merged"
        assert _merged_into(other) == primary.id
