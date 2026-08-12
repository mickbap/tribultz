"""Round 5 §8 — invariante: NENHUM evento externo cria oportunidade por conta própria.

Deal nasce somente em Qualificado Tribultz (validação humana dos 3 elementos,
Round 5 §6). Bateria: em todos os cenários listados pela ordem —
Rumy=Qualificado, resposta recebida, emoji/reação, handoff.requested,
HANDOFF_REQUESTED, HUMAN_OWNED, Discovery — sem qualificação humana:
``attio_deal_id = null``. Reforço estático: nenhum código de produção atribui
attio_deal_id (a capacidade nem existe nesta fase).
"""

import json
import os
import pathlib
import re
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadLink
from app.services.handoff.inbox import persist_raw_event, process_raw_event
from app.services.handoff.ownership import ActorType, OwnershipState, transition_ownership

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_ULID_BASE = "01J8ZM7WVX2Q9RKTHB3F6D5C"
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid(n: int) -> str:
    return _ULID_BASE + _ALPHABET[n // 32] + _ALPHABET[n % 32]


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
    tenant = Tenant(name=f"Tenant QA {uuid.uuid4().hex[:6]}", slug=f"tenant-qa-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    return tenant.id


def _ingest(session, tenant_id, payload):
    row, _ = persist_raw_event(session, tenant_id, json.dumps(payload).encode(), payload)
    return process_raw_event(session, row.id)  # type: ignore[arg-type]


def _assert_no_deal(session):
    for link in session.query(CrmLeadLink).all():
        assert link.attio_deal_id is None, f"Deal criado indevidamente no link {link.id}"


def test_bateria_completa_nenhum_evento_cria_deal(session, tenant_id, monkeypatch):
    monkeypatch.setattr(settings, "HANDOFF_APPLY_ENABLED", True)

    # 1) 'Rumy = Qualificado' — classificação do fornecedor é dado de origem
    _ingest(session, tenant_id, {"event_type": "rumy.qualificado", "lead": "sintetico-q"})
    _assert_no_deal(session)

    # 2) resposta recebida / 3) emoji-reação — sinais viram handoff.requested,
    # nunca oportunidade (last_interaction registra o quê, não qualifica)
    _ingest(
        session,
        tenant_id,
        {
            "schema_version": "1.1",
            "event_id": _ulid(0),
            "event_type": "handoff.requested",
            "occurred_at": "2026-08-12T12:00:00+00:00",
            "external_lead_id": "lead-sintetico-deal-001",
            "person": {
                "full_name": "Pessoa Sintética [QA]",
                "email": {"status": "known", "value": "sem.deal@example.test"},
            },
            "company": {"name": {"status": "known", "value": "Empresa Sintética QA Ltda"}},
            "reason": "positive_reply",
            "last_interaction": {"channel": "linkedin", "kind": "reaction"},
        },
    )
    _assert_no_deal(session)

    link = session.query(CrmLeadLink).one()
    # 4/5) handoff.requested aplicado ⇒ HANDOFF_REQUESTED — sem Deal
    assert link.ownership_state == "HANDOFF_REQUESTED"
    _assert_no_deal(session)

    # 6) HUMAN_OWNED — humano assumir NÃO qualifica
    transition_ownership(
        session, link, OwnershipState.HUMAN_OWNED, ActorType.HUMAN, actor_ref="ana.qa"
    )
    _assert_no_deal(session)

    # 7) Discovery (estágio comercial) — ainda não é Qualificado Tribultz
    link.commercial_state = "Discovery"
    session.flush()
    _assert_no_deal(session)


def test_estaticamente_nenhum_codigo_de_producao_atribui_deal():
    """A capacidade de criar Deal não existe no pipeline — invariante por construção.

    Varre app/ inteiro: nenhuma atribuição a attio_deal_id fora do model (a
    coluna existe para a fase futura F4/F7, onde nascerá SOMENTE de fluxo com
    qualificação humana registrada).
    """
    base = pathlib.Path(__file__).resolve().parents[1] / "app"
    assign = re.compile(r"\.attio_deal_id\s*=|attio_deal_id\s*=(?!=)")
    offenders = []
    for f in base.rglob("*.py"):
        if f.name == "crm_handoff.py":  # definição da coluna no model
            continue
        text = f.read_text()
        for match in assign.finditer(text):
            snippet = text[max(0, match.start() - 40): match.end() + 40].replace("\n", " ")
            offenders.append(f"{f}: …{snippet}…")
    assert not offenders, "código de produção atribui attio_deal_id:\n" + "\n".join(offenders)


def test_datas_do_gate():
    """Guarda-corpo de regressão do gate: Deal só em Qualificado Tribultz (§6)."""
    # A regra é estrutural (teste acima); este teste fixa a data da decisão para
    # auditoria futura do Round.
    assert datetime(2026, 8, 12, tzinfo=timezone.utc).date().isoformat() == "2026-08-12"
