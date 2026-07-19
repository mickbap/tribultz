"""Cockpit Operacional do Programa Early Adopters (RFC-0024) — Tela 02.

Cobre o que a RFC-0024 adiciona sobre a fundação já testada em
test_founding_partners_admin.py (RFC-0017/ADR-0008): perfil detalhado (jornada
auto+manual, Customer Evidence, TERA), próxima ação/owner/reconhecimento,
interesse de conversão e o gatilho de conversão via ASAAS (mockado — nunca bate
na API real do Asaas em teste).
"""

import os
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.billing import Payment, Subscription

anon = TestClient(app)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")


def _pg_available() -> bool:
    try:
        with create_engine(DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark_db = pytest.mark.skipif(not _pg_available(), reason="Postgres indisponível (roda no CI)")

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


@pytest.fixture(name="client")
def client_fixture(session):
    from app.api.deps import get_current_user

    tenant = Tenant(name="Admin", slug=f"admin-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    admin = User(
        tenant_id=tenant.id, email=f"owner-{uuid.uuid4().hex[:8]}@tribultz.com.br",
        full_name="Owner", password_hash=get_password_hash("x"), role="superadmin", email_verified=True,
    )
    session.add(admin)
    session.flush()

    def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.clear()


def _admit(client, cnpj: str | None = "11222333000181") -> dict:
    email = f"ea-{uuid.uuid4().hex[:8]}@empresa.com"
    hoje = date.today()
    r = client.post("/api/v1/admin/founding-partners", json={
        "empresa": "Cockpit Ltda", "email": email, "cnpj": cnpj,
        "initial_password": "SenhaForte1", "responsavel": "Ana", "origem": "linkedin",
        "grant": {"plan_slug": "contador", "starts_on": hoje.isoformat(), "ends_on": (hoje + timedelta(days=90)).isoformat()},
    })
    assert r.status_code == 201, r.text
    return r.json()


# ── Gate (sem DB) ─────────────────────────────────────────────────────────────

_UUID = "00000000-0000-0000-0000-000000000000"
NEW_ENDPOINTS = [
    ("get", f"/api/v1/admin/founding-partners/{_UUID}", None),
    ("post", f"/api/v1/admin/founding-partners/{_UUID}/journey", {"stage": "selecionado"}),
    ("post", f"/api/v1/admin/founding-partners/{_UUID}/evidence", {"tipo": "insight", "texto": "x"}),
    ("patch", f"/api/v1/admin/founding-partners/{_UUID}/conversion", {"interesse": "sim"}),
    ("post", f"/api/v1/admin/founding-partners/{_UUID}/convert", {"plan_slug": "starter"}),
    ("get", f"/api/v1/admin/founding-partners/tera/{_UUID}/download", None),
]


def test_novos_endpoints_registrados_e_superadmin_only():
    for method, path, body in NEW_ENDPOINTS:
        resp = getattr(anon, method)(path, json=body) if body is not None else anon.get(path)
        assert resp.status_code != 404, f"{method} {path} não registrado"
        assert resp.status_code in (401, 403), f"{method} {path} deveria bloquear anônimo ({resp.status_code})"


# ── Tela 02 — perfil, jornada, evidence, TERA ──────────────────────────────────


@pytestmark_db
def test_detalhe_traz_jornada_evidence_tera_vazios(client, session):
    ea = _admit(client)
    r = client.get(f"/api/v1/admin/founding-partners/{ea['id']}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["journey"] == []
    assert body["customer_evidence"] == []
    assert body["tera"] == []
    assert body["recognition"] == "early_adopter"
    assert body["system"]["first_login_at"] is None


@pytestmark_db
def test_jornada_auto_primeiro_login_derivada_ao_vivo(client, session):
    ea = _admit(client)
    user = session.execute(select(User).where(User.email == ea["email"])).scalar_one()
    user.first_login_at = datetime.now(timezone.utc)
    session.commit()

    r = client.get(f"/api/v1/admin/founding-partners/{ea['id']}")
    stages = [e["stage"] for e in r.json()["journey"]]
    assert "primeiro_login" in stages
    auto = next(e for e in r.json()["journey"] if e["stage"] == "primeiro_login")
    assert auto["source"] == "auto"
    assert auto["id"] is None  # nunca persistido — derivado ao vivo


@pytestmark_db
def test_jornada_manual_registrada_e_valida_etapa(client, session):
    ea = _admit(client)
    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/journey", json={"stage": "selecionado", "note": "Reunião marcada"})
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "manual"

    bad = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/journey", json={"stage": "etapa_inexistente"})
    assert bad.status_code == 400

    detail = client.get(f"/api/v1/admin/founding-partners/{ea['id']}")
    assert any(e["stage"] == "selecionado" for e in detail.json()["journey"])


@pytestmark_db
def test_customer_evidence_criada_e_valida_tipo(client, session):
    ea = _admit(client)
    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/evidence", json={
        "tipo": "momento_wow", "texto": "Adorou o laudo em PDF",
    })
    assert r.status_code == 201, r.text
    assert r.json()["tipo"] == "momento_wow"

    bad = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/evidence", json={"tipo": "tipo_invalido", "texto": "x"})
    assert bad.status_code == 400

    empty_text = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/evidence", json={"tipo": "insight", "texto": "   "})
    assert empty_text.status_code == 400


@pytestmark_db
def test_tera_registro_manual_via_link_sem_arquivo(client, session):
    ea = _admit(client)
    r = client.post(
        f"/api/v1/admin/founding-partners/{ea['id']}/tera",
        data={"versao": "v1", "tera_status": "rascunho", "pdf_link": "https://drive.example/tera-v1.pdf"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["has_file"] is False
    assert body["pdf_link"] == "https://drive.example/tera-v1.pdf"

    tera_id = body["id"]
    dl = client.get(f"/api/v1/admin/founding-partners/tera/{tera_id}/download")
    assert dl.status_code == 400, "TERA só com link (sem storage_key) não deve gerar URL presignada"


@pytestmark_db
def test_tera_status_invalido_rejeitado(client, session):
    ea = _admit(client)
    r = client.post(
        f"/api/v1/admin/founding-partners/{ea['id']}/tera",
        data={"versao": "v1", "tera_status": "publicado"},
    )
    assert r.status_code == 400


# ── Cadastrais expandidos, próxima ação, owner, reconhecimento ────────────────


@pytestmark_db
def test_update_cadastrais_expandidos_e_reconhecimento(client, session):
    ea = _admit(client)
    r = client.patch(f"/api/v1/admin/founding-partners/{ea['id']}", json={
        "cargo": "CFO", "cidade": "São Paulo", "uf": "SP", "erp": "Domínio",
        "qtd_cnpjs": 3, "volume_nfe_mensal_aprox": 500,
        "proxima_acao": "Ligar terça", "owner_email": "mickel@tribultz.com.br",
        "recognition": "founding_partner",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cargo"] == "CFO"
    assert body["uf"] == "SP"
    assert body["qtd_cnpjs"] == 3
    assert body["proxima_acao"] == "Ligar terça"
    assert body["recognition"] == "founding_partner"


@pytestmark_db
def test_update_recognition_invalido_rejeitado(client, session):
    ea = _admit(client)
    r = client.patch(f"/api/v1/admin/founding-partners/{ea['id']}", json={"recognition": "vip"})
    assert r.status_code == 400


# ── Conversão ────────────────────────────────────────────────────────────────


@pytestmark_db
def test_conversion_interest_registrado_sem_asaas(client, session):
    ea = _admit(client)
    r = client.patch(f"/api/v1/admin/founding-partners/{ea['id']}/conversion", json={"interesse": "pensando", "motivo": "avaliando orçamento"})
    assert r.status_code == 200, r.text
    assert r.json()["conversion"]["interesse"] == "pensando"

    bad = client.patch(f"/api/v1/admin/founding-partners/{ea['id']}/conversion", json={"interesse": "talvez"})
    assert bad.status_code == 400


@pytestmark_db
def test_convert_sem_cnpj_bloqueado_antes_do_asaas(client, session, monkeypatch):
    ea = _admit(client, cnpj=None)
    create_customer = AsyncMock()
    monkeypatch.setattr("app.routers.founding_partners.asaas.create_customer", create_customer)

    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/convert", json={"plan_slug": "starter"})
    assert r.status_code == 400
    create_customer.assert_not_called()


@pytestmark_db
def test_convert_plano_gratuito_rejeitado(client, session):
    ea = _admit(client)
    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/convert", json={"plan_slug": "trial"})
    assert r.status_code == 400


@pytestmark_db
def test_convert_reusa_asaas_cria_subscription_e_marca_conversao(client, session, monkeypatch):
    ea = _admit(client)

    monkeypatch.setattr(
        "app.routers.founding_partners.asaas.create_customer",
        AsyncMock(return_value={"id": "cus_mock_123"}),
    )
    monkeypatch.setattr(
        "app.routers.founding_partners.asaas.create_subscription",
        AsyncMock(return_value={"id": "sub_mock_456"}),
    )
    monkeypatch.setattr(
        "app.routers.founding_partners.asaas.get_subscription_payments",
        AsyncMock(return_value=[{"id": "pay_mock_789"}]),
    )
    monkeypatch.setattr(
        "app.routers.founding_partners.asaas.get_pix_qr_code",
        AsyncMock(return_value={"encodedImage": "base64img", "payload": "pix-copia-cola"}),
    )

    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/convert", json={
        "plan_slug": "starter", "billing_type": "PIX", "motivo": "gostou do produto", "origem": "cockpit",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pix_qr_code"] == "base64img"
    assert body["early_adopter"]["conversion"]["interesse"] == "sim"
    assert body["early_adopter"]["conversion"]["plano_slug"] == "starter"

    sub = session.execute(
        select(Subscription).where(Subscription.id == uuid.UUID(body["subscription_id"]))
    ).scalar_one()
    assert sub.status == "pending"
    assert sub.asaas_subscription_id == "sub_mock_456"
    payment = session.execute(
        select(Payment).where(Payment.subscription_id == sub.id)
    ).scalar_one()
    assert payment.amount_cents == 4990  # preço do plano "starter"


@pytestmark_db
def test_convert_nunca_cria_gateway_paralelo_so_chama_asaas(client, session, monkeypatch):
    """Guardrail RFC-0024: 'proibido gateway paralelo' — garante que a conversão
    só invoca o módulo `asaas`, nunca outro serviço de pagamento."""
    ea = _admit(client)
    calls: list[str] = []

    async def _create_customer(**kw):
        calls.append("create_customer")
        return {"id": "cus_x"}

    async def _create_subscription(**kw):
        calls.append("create_subscription")
        return {"id": "sub_x"}

    async def _get_payments(sub_id):
        calls.append("get_subscription_payments")
        return [{"id": "pay_x"}]

    async def _get_pix(payment_id):
        calls.append("get_pix_qr_code")
        return {"encodedImage": "img", "payload": "copia-cola"}

    monkeypatch.setattr("app.routers.founding_partners.asaas.create_customer", _create_customer)
    monkeypatch.setattr("app.routers.founding_partners.asaas.create_subscription", _create_subscription)
    monkeypatch.setattr("app.routers.founding_partners.asaas.get_subscription_payments", _get_payments)
    monkeypatch.setattr("app.routers.founding_partners.asaas.get_pix_qr_code", _get_pix)

    r = client.post(f"/api/v1/admin/founding-partners/{ea['id']}/convert", json={"plan_slug": "starter"})
    assert r.status_code == 200, r.text
    assert calls == ["create_customer", "create_subscription", "get_subscription_payments", "get_pix_qr_code"]
