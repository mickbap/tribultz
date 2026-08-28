"""#691 — reconciliação Attio ↔ domínio por external_lead_id (Fatia 1, Round 16-G).

Prova as fronteiras que a ordem fixou: liga vínculo, não cria pessoa, não toca
fase/ownership/histórico, e trata divergência como relatório — nunca escolha
heurística.

Dados 100% sintéticos. Nenhuma chamada ao Attio real; nenhuma flag habilitada.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadLink
from app.services.handoff.reconciliation import AttioEntry, reconcile_attio_links

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="tenant_id")
def tenant_fixture(session):
    t = Tenant(name=f"T691 {uuid.uuid4().hex[:6]}", slug=f"t691-{uuid.uuid4()}")
    session.add(t)
    session.flush()
    return t.id


def _link(session, tenant_id, external_id, **kw):
    link = CrmLeadLink(
        tenant_id=tenant_id,
        source_system="rumy",
        external_lead_id=external_id,
        ownership_state=kw.pop("ownership_state", "AUTOMATED"),
        **kw,
    )
    session.add(link)
    session.flush()
    return link


class TestVinculo:
    def test_dry_run_relata_sem_escrever(self, session, tenant_id):
        link = _link(session, tenant_id, "lead_a")
        r = reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_1")], dry_run=True
        )
        assert r.linked == ["lead_a"] and r.dry_run is True
        assert link.attio_person_id is None, "dry-run não pode escrever"

    def test_aplica_quando_pedido_explicitamente(self, session, tenant_id):
        link = _link(session, tenant_id, "lead_a")
        r = reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_1", "company_1")], dry_run=False
        )
        assert r.linked == ["lead_a"]
        assert link.attio_person_id == "person_1"
        assert link.attio_company_id == "company_1"

    def test_idempotente(self, session, tenant_id):
        _link(session, tenant_id, "lead_a")
        e = [AttioEntry("lead_a", "person_1")]
        reconcile_attio_links(session, tenant_id, e, dry_run=False)
        r2 = reconcile_attio_links(session, tenant_id, e, dry_run=False)
        assert r2.already_linked == ["lead_a"] and r2.linked == []

    def test_company_so_quando_inequivoca(self, session, tenant_id):
        """Company já preenchida no domínio não é sobrescrita pelo espelho."""
        link = _link(session, tenant_id, "lead_a", attio_company_id="company_ja_existente")
        reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_1", "company_outra")], dry_run=False
        )
        assert link.attio_company_id == "company_ja_existente"


class TestFailClosed:
    def test_conflito_nao_sobrescreve(self, session, tenant_id):
        link = _link(session, tenant_id, "lead_a", attio_person_id="person_dominio")
        r = reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_attio")], dry_run=False
        )
        assert r.conflict and r.conflict[0]["external_lead_id"] == "lead_a"
        assert link.attio_person_id == "person_dominio", "conflito nunca sobrescreve"
        assert r.linked == []

    def test_ambiguidade_nao_escolhe_heuristicamente(self, session, tenant_id):
        link = _link(session, tenant_id, "lead_a")
        r = reconcile_attio_links(
            session,
            tenant_id,
            [AttioEntry("lead_a", "person_1"), AttioEntry("lead_a", "person_2")],
            dry_run=False,
        )
        assert r.ambiguous == ["lead_a"]
        assert link.attio_person_id is None, "duas verdades ⇒ nenhuma escolha"

    def test_orfao_no_attio_e_relatado_nunca_criado(self, session, tenant_id):
        """Sintético do 23/08 cai aqui: existe no Attio, não no domínio."""
        r = reconcile_attio_links(
            session,
            tenant_id,
            [AttioEntry("lead_FIRSTARTICLE-2C2A-SINTETICO", "person_x")],
            dry_run=False,
        )
        assert r.orphan_in_attio == ["lead_FIRSTARTICLE-2C2A-SINTETICO"]
        assert session.query(CrmLeadLink).count() == 0, "espelho não cria no domínio"


class TestNaoTocaOutrosEixos:
    def test_ownership_fase_e_historico_intactos(self, session, tenant_id):
        link = _link(
            session, tenant_id, "lead_a",
            ownership_state="HUMAN_OWNED", commercial_state="Discovery",
            automation_state="PAUSED", owner_ref="humano.qa",
        )
        reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_1")], dry_run=False
        )
        assert link.ownership_state == "HUMAN_OWNED"
        assert link.commercial_state == "Discovery"
        assert link.automation_state == "PAUSED"
        assert link.owner_ref == "humano.qa"

    def test_isolamento_entre_tenants(self, session, tenant_id):
        outro = Tenant(name="Outro T691", slug=f"outro-{uuid.uuid4()}")
        session.add(outro)
        session.flush()
        link_outro = _link(session, outro.id, "lead_a")
        r = reconcile_attio_links(
            session, tenant_id, [AttioEntry("lead_a", "person_1")], dry_run=False
        )
        assert r.orphan_in_attio == ["lead_a"]
        assert link_outro.attio_person_id is None


class TestFlagsPermanecemOff:
    def test_nenhuma_flag_ligada_por_esta_fatia(self):
        from app.config import Settings

        for flag in ("ATTIO_ENABLED", "RUMY_WEBHOOK_ENABLED", "HANDOFF_APPLY_ENABLED"):
            assert Settings.model_fields[flag].default is False, flag
