"""Filtro de supressão (PO-2026-07-SALES-001, Fase 1) — DB-backed."""

import os
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.prospect_org import ProspectOrg
from app.models.prospect_suppression import ProspectSuppression
from app.services.prospecting.suppression import (
    DEFAULT_EXCLUDE_STATUSES,
    filter_candidates,
)

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


def _make_org(session, *, cnpj_basico=None, email_domain=None) -> ProspectOrg:
    cnpj_basico = cnpj_basico or uuid.uuid4().hex[:8]
    org = ProspectOrg(
        cnpj_basico=cnpj_basico,
        cnpj_matriz=f"{cnpj_basico}000191",
        razao_social=f"Empresa {cnpj_basico}",
        porte="05",
        capital_social=Decimal("0"),
        situacao_cadastral="02",
        qtd_estabelecimentos=1,
        uf="RS",
        email_domain=email_domain,
        email_domain_category="dominio_nominal" if email_domain else "ausente",
        cnae_principal="6920601",
        source_dump_reference="test",
    )
    session.add(org)
    session.flush()
    return org


def _suppress(session, *, cnpj_basico=None, email_domain=None, status="opt_out"):
    row = ProspectSuppression(cnpj_basico=cnpj_basico, email_domain=email_domain, status=status)
    session.add(row)
    session.flush()
    return row


class TestMandatoryExclusion:
    def test_opt_out_by_cnpj_basico_is_always_excluded(self, session):
        org = _make_org(session, cnpj_basico="10000001")
        _suppress(session, cnpj_basico="10000001", status="opt_out")

        result = filter_candidates(session, [org], exclude_statuses=frozenset())
        assert org not in result

    def test_cliente_by_email_domain_is_always_excluded(self, session):
        org = _make_org(session, email_domain="jacliente.com.br")
        _suppress(session, email_domain="jacliente.com.br", status="cliente")

        result = filter_candidates(session, [org], exclude_statuses=frozenset())
        assert org not in result

    def test_mandatory_exclusion_cannot_be_disabled_via_flag(self, session):
        """opt_out/cliente são aplicados mesmo se exclude_statuses vier vazio —
        não existe flag de CLI que os desative."""
        org = _make_org(session, cnpj_basico="10000002")
        _suppress(session, cnpj_basico="10000002", status="opt_out")

        result = filter_candidates(session, [org], exclude_statuses=frozenset())
        assert result == []


class TestConfigurableExclusion:
    def test_lead_ativo_excluded_by_default(self, session):
        org = _make_org(session, cnpj_basico="20000001")
        _suppress(session, cnpj_basico="20000001", status="lead_ativo")

        result = filter_candidates(session, [org], exclude_statuses=DEFAULT_EXCLUDE_STATUSES)
        assert org not in result

    def test_desqualificado_excluded_by_default(self, session):
        org = _make_org(session, cnpj_basico="20000002")
        _suppress(session, cnpj_basico="20000002", status="desqualificado")

        result = filter_candidates(session, [org], exclude_statuses=DEFAULT_EXCLUDE_STATUSES)
        assert org not in result

    def test_lead_ativo_included_when_status_not_in_exclude_set(self, session):
        org = _make_org(session, cnpj_basico="20000003")
        _suppress(session, cnpj_basico="20000003", status="lead_ativo")

        # Operador explicitamente NÃO pede exclusão de lead_ativo desta vez.
        result = filter_candidates(session, [org], exclude_statuses=frozenset())
        assert org in result


class TestHardBounceAlwaysExcluded:
    def test_hard_bounce_excluded_by_default(self, session):
        org = _make_org(session, cnpj_basico="30000001")
        _suppress(session, cnpj_basico="30000001", status="hard_bounce")

        result = filter_candidates(session, [org], exclude_statuses=DEFAULT_EXCLUDE_STATUSES)
        assert org not in result

    def test_hard_bounce_excluded_when_explicitly_requested(self, session):
        org = _make_org(session, cnpj_basico="30000002")
        _suppress(session, cnpj_basico="30000002", status="hard_bounce")

        result = filter_candidates(
            session, [org], exclude_statuses=DEFAULT_EXCLUDE_STATUSES | frozenset({"hard_bounce"})
        )
        assert org not in result

    def test_hard_bounce_cannot_be_disabled(self, session):
        org = _make_org(session, cnpj_basico="30000003")
        _suppress(session, cnpj_basico="30000003", status="hard_bounce")

        assert filter_candidates(session, [org], exclude_statuses=frozenset()) == []


class TestNoSuppressionMatch:
    def test_org_without_any_suppression_row_passes_through(self, session):
        org = _make_org(session, cnpj_basico="40000001", email_domain="livre.com.br")
        result = filter_candidates(session, [org])
        assert org in result
