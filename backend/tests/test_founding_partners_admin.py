"""Founding Partners — Command Center: gate + fluxo do Grant (RFC-0017 / ADR-0008).

- Gate: os endpoints são superadmin-only.
- Integração (Postgres, como o CI): admite empresa, concede Plano Contador via
  Grant (sem Subscription ASAAS), resolve a licença, expira/revoga → reverte,
  encerra. Cobre os critérios de aceite da ordem.
"""

import os
import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.billing import Subscription
from app.models.founding_partner import (
    resolve_effective_license,
)

anon = TestClient(app)

# ── Gate (sem DB) ─────────────────────────────────────────────────────────────

_UUID = "00000000-0000-0000-0000-000000000000"
ENDPOINTS = [
    ("get", "/api/v1/admin/founding-partners", None),
    ("post", "/api/v1/admin/founding-partners", {"empresa": "X", "email": "x@y.com", "initial_password": "12345678"}),
    ("patch", f"/api/v1/admin/founding-partners/{_UUID}", {"empresa": "Y"}),
    ("post", f"/api/v1/admin/founding-partners/{_UUID}/grants", {"starts_on": "2026-07-08", "ends_on": "2026-08-08"}),
    ("post", f"/api/v1/admin/founding-partners/grants/{_UUID}/revoke", {}),
    ("post", f"/api/v1/admin/founding-partners/{_UUID}/close", {}),
]


def test_endpoints_registrados_e_superadmin_only():
    for method, path, body in ENDPOINTS:
        resp = getattr(anon, method)(path, json=body) if body is not None else anon.get(path)
        assert resp.status_code != 404, f"{method} {path} não registrado"
        assert resp.status_code in (401, 403), f"{method} {path} deveria bloquear anônimo ({resp.status_code})"


# ── Integração DB ─────────────────────────────────────────────────────────────

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


@pytestmark_db
def test_fluxo_completo_grant(client, session):
    email = f"fp-{uuid.uuid4().hex[:8]}@empresa.com"
    hoje = date(2026, 7, 8)
    # 1. Admite empresa já com Grant (Plano Contador, vigência).
    r = client.post("/api/v1/admin/founding-partners", json={
        "empresa": "Contabilidade Duquesa", "email": email, "origem": "indicacao",
        "initial_password": "SenhaForte1", "responsavel": "Kátia",
        "grant": {"plan_slug": "contador", "starts_on": hoje.isoformat(), "ends_on": (hoje + timedelta(days=30)).isoformat()},
    })
    assert r.status_code == 201, r.text
    ea = r.json()
    assert ea["effective_plan"] == "contador"
    tenant_id = uuid.UUID(ea["tenant_id"])

    # 2. Usuário de login provisionado, SEM Subscription (guardrail ASAAS).
    user = session.execute(select(User).where(User.email == email)).scalar_one()
    assert user.email_verified is True
    subs = session.scalar(select(func.count(Subscription.id)).where(Subscription.tenant_id == tenant_id))
    assert subs == 0, "Grant nunca cria Subscription (RNF002)"

    # 3. Grant Adapter resolve Contador no login (sem assinatura).
    plan, source = resolve_effective_license(session, tenant_id, "trial")
    assert (plan, source) == ("contador", "early_grant")

    # 4. Revogação → reverte para a assinatura (trial).
    grant_id = ea["active_grant_id"]
    assert client.post(f"/api/v1/admin/founding-partners/grants/{grant_id}/revoke").status_code == 200
    plan, source = resolve_effective_license(session, tenant_id, "trial")
    assert (plan, source) == ("trial", "subscription")


@pytestmark_db
def test_expiracao_lazy_reverte_sem_beat(client, session):
    email = f"fp-{uuid.uuid4().hex[:8]}@empresa.com"
    r = client.post("/api/v1/admin/founding-partners", json={
        "empresa": "Expira Ltda", "email": email, "initial_password": "SenhaForte1",
    })
    ea_id = r.json()["id"]
    tenant_id = uuid.UUID(r.json()["tenant_id"])
    # Grant que já venceu (ends_on no passado): concede e verifica que NÃO resolve.
    ontem = date.today() - timedelta(days=2)
    g = client.post(f"/api/v1/admin/founding-partners/{ea_id}/grants", json={
        "starts_on": (ontem - timedelta(days=5)).isoformat(), "ends_on": ontem.isoformat(),
    })
    assert g.status_code == 201
    plan, source = resolve_effective_license(session, tenant_id, "starter")
    assert (plan, source) == ("starter", "subscription"), "grant vencido não deve resolver (expiração lazy)"


@pytestmark_db
def test_encerramento_revoga_e_bloqueia(client, session):
    email = f"fp-{uuid.uuid4().hex[:8]}@empresa.com"
    hoje = date.today()
    r = client.post("/api/v1/admin/founding-partners", json={
        "empresa": "Encerra Ltda", "email": email, "initial_password": "SenhaForte1",
        "grant": {"starts_on": hoje.isoformat(), "ends_on": (hoje + timedelta(days=30)).isoformat()},
    })
    ea_id = r.json()["id"]
    tenant_id = uuid.UUID(r.json()["tenant_id"])
    assert resolve_effective_license(session, tenant_id, "trial")[0] == "contador"
    # Encerra o programa → revoga o Grant ativo → acesso reverte.
    close = client.post(f"/api/v1/admin/founding-partners/{ea_id}/close")
    assert close.status_code == 200 and close.json()["status"] == "closed"
    assert resolve_effective_license(session, tenant_id, "trial")[0] == "trial"
