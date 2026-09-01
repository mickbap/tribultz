"""Growth P0 / Resend: gates, dry-run e feedback de suppression (#733)."""

from __future__ import annotations

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from svix.webhooks import Webhook

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.auth import Tenant
from app.models.crm_handoff import CrmLeadLink, CrmPersonIdentity
from app.models.prospect_org import ProspectOrg
from app.models.prospect_suppression import ProspectSuppression
from app.models.resend_webhook_event import ResendWebhookEvent
from app.services.growth.resend_p0 import MarketingState, build_dry_run, decide_marketing_state

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
SECRET = "whsec_" + base64.b64encode(b"segredo-sintetico-resend-32bytes!").decode()


@pytest.fixture()
def session():
    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


def _org(session, *, email: str | None = None, eligible: bool = True, origin: str | None = "RECEITA_FEDERAL_DADOS_ABERTOS") -> ProspectOrg:
    key = uuid.uuid4().hex[:8]
    email = email or f"contato-{key}@example.test"
    org = ProspectOrg(
        cnpj_basico=key,
        cnpj_matriz=f"{key}000191",
        razao_social=f"Empresa {key}",
        porte="05",
        capital_social=Decimal("0"),
        situacao_cadastral="02",
        qtd_estabelecimentos=1,
        uf="RS",
        email=email,
        email_domain=email.rsplit("@", 1)[1] if email else None,
        email_domain_category="dominio_nominal",
        cnae_principal="6920601",
        source_dump_reference="test",
        marketing_origin=origin,
        marketing_purpose="PROSPECCAO_COMERCIAL_B2B",
        marketing_legal_basis="DECISAO_JURIDICA_REGISTRADA",
        marketing_eligibility="ELIGIBLE" if eligible else "INELIGIBLE",
        marketing_eligibility_reason="fixture_aprovada" if eligible else "fixture_reprovada",
        marketing_eligibility_evaluated_at=datetime.now(timezone.utc),
    )
    session.add(org)
    session.flush()
    return org


def test_origem_desconhecida_e_inelegivel_nao_enviam(session):
    unknown = _org(session, origin=None)
    ineligible = _org(session, eligible=False)

    assert decide_marketing_state(unknown, [], set()).state == MarketingState.INELIGIBLE
    assert decide_marketing_state(ineligible, [], set()).state == MarketingState.INELIGIBLE


def test_suppressed_nao_envia_e_match_de_email_e_exato(session):
    org = _org(session, email="Pessoa@Example.Test")
    suppression = ProspectSuppression(email="pessoa@example.test", status="opt_out")
    session.add(suppression)
    session.flush()

    assert decide_marketing_state(org, [suppression], set()).state == MarketingState.SUPPRESSED


def test_controle_humano_nao_envia(session):
    org = _org(session, email="humano@example.test")
    decision = decide_marketing_state(org, [], {"humano@example.test"})

    assert decision.state == MarketingState.SUPPRESSED
    assert decision.human_controlled is True


def test_dry_run_contabiliza_elegivel_e_enviavel(session):
    _org(session, email="enviavel@example.test")
    _org(session, email="inelegivel@example.test", eligible=False)
    suppressed = _org(session, email="suprimido@example.test")
    session.add(ProspectSuppression(email=suppressed.email, status="opt_out"))
    session.flush()

    result = build_dry_run(session).as_dict()

    assert result == {
        "TOTAL_BASE": 3,
        "ELIGIBLE": 2,
        "INELIGIBLE": 1,
        "SUPPRESSED": 1,
        "CONTROLE_HUMANO": 0,
        "TOTAL_ENVIAVEL": 1,
    }


def test_dry_run_identifica_controle_humano_no_dominio_existente(session):
    email = "ownership@example.test"
    _org(session, email=email)
    tenant = Tenant(name="Growth P0", slug=f"growth-p0-{uuid.uuid4().hex}")
    session.add(tenant)
    session.flush()
    person = CrmPersonIdentity(tenant_id=tenant.id, email_normalized=email)
    session.add(person)
    session.flush()
    session.add(
        CrmLeadLink(
            tenant_id=tenant.id,
            external_lead_id=f"lead-{uuid.uuid4()}",
            person_identity_id=person.id,
            ownership_state="HUMAN_OWNED",
            automation_state="PAUSED",
        )
    )
    session.flush()

    result = build_dry_run(session)
    assert result.CONTROLE_HUMANO == 1
    assert result.SUPPRESSED == 1
    assert result.TOTAL_ENVIAVEL == 0


@pytest.fixture()
def client(session, monkeypatch):
    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(session, "commit", session.flush)
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_ENABLED", True)
    monkeypatch.setattr(settings, "RESEND_WEBHOOK_SECRET", SECRET)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _signed_headers(body: bytes, event_id: str) -> dict[str, str]:
    timestamp = datetime.now(timezone.utc)
    signature = Webhook(SECRET).sign(event_id, timestamp, body.decode())
    return {
        "svix-id": event_id,
        "svix-timestamp": str(int(timestamp.timestamp())),
        "svix-signature": signature,
        "content-type": "application/json",
    }


def test_unsubscribe_resend_vira_suppression_tribultz_idempotente(client, session):
    email = "unsubscribe@example.test"
    body = json.dumps(
        {
            "type": "contact.updated",
            "created_at": "2026-09-01T12:00:00.000Z",
            "data": {"id": "contact_1", "email": email, "unsubscribed": True},
        },
        separators=(",", ":"),
    ).encode()
    headers = _signed_headers(body, "msg_unsubscribe_1")

    first = client.post("/api/v1/webhooks/resend", content=body, headers=headers)
    replay = client.post("/api/v1/webhooks/resend", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["status"] == "applied"
    assert replay.status_code == 200
    assert replay.json()["status"] == "duplicate"
    rows = session.execute(
        select(ProspectSuppression).where(ProspectSuppression.email == email)
    ).scalars().all()
    assert [(row.status, row.source) for row in rows] == [("opt_out", "resend")]
    assert session.query(ResendWebhookEvent).filter_by(svix_id="msg_unsubscribe_1").count() == 1


def test_bounce_permanente_bloqueia_novo_marketing(client, session):
    email = "bounce@example.test"
    org = _org(session, email=email)
    body = json.dumps(
        {
            "type": "email.bounced",
            "created_at": "2026-09-01T12:00:00.000Z",
            "data": {"email_id": "email_1", "to": [email], "bounce": {"type": "Permanent"}},
        },
        separators=(",", ":"),
    ).encode()

    response = client.post(
        "/api/v1/webhooks/resend",
        content=body,
        headers=_signed_headers(body, "msg_bounce_1"),
    )
    suppressions = session.execute(select(ProspectSuppression)).scalars().all()

    assert response.status_code == 200
    assert suppressions[0].status == "hard_bounce"
    assert decide_marketing_state(org, suppressions, set()).state == MarketingState.SUPPRESSED


def test_resend_nao_pode_remover_suppression_canonica(client, session):
    email = "canonico@example.test"
    session.add(ProspectSuppression(email=email, status="opt_out", source="tribultz"))
    session.flush()
    body = json.dumps(
        {
            "type": "contact.updated",
            "created_at": "2026-09-01T12:00:00.000Z",
            "data": {"id": "contact_2", "email": email, "unsubscribed": False},
        },
        separators=(",", ":"),
    ).encode()

    response = client.post(
        "/api/v1/webhooks/resend",
        content=body,
        headers=_signed_headers(body, "msg_resubscribe_1"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert session.query(ProspectSuppression).filter_by(email=email).count() == 1


def test_reimportacao_nao_ressuscita_suppressed(session):
    org = _org(session, email="persistente@example.test")
    row = ProspectSuppression(email=org.email, status="opt_out", source="resend")
    session.add(row)
    session.flush()

    # A importação só atualiza prospect_orgs; suppression vive em tabela
    # canônica separada e permanece com precedência após atualizar a base.
    org.source_dump_reference = "dump-seguinte"  # type: ignore[assignment]
    org.razao_social = "Empresa atualizada pela reimportação"  # type: ignore[assignment]
    session.flush()

    assert session.get(ProspectSuppression, row.id) is row
    assert decide_marketing_state(org, [row], set()).state == MarketingState.SUPPRESSED


def test_assinatura_invalida_nao_persiste(client, session):
    response = client.post(
        "/api/v1/webhooks/resend",
        content=b'{"type":"contact.updated"}',
        headers={
            "svix-id": "msg_invalida",
            "svix-timestamp": "1788264000",
            "svix-signature": "v1,invalida",
        },
    )
    assert response.status_code == 401
    assert session.query(ResendWebhookEvent).filter_by(svix_id="msg_invalida").count() == 0
