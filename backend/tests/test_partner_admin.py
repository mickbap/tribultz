"""Partner Attribution v1 (RFC-0025) — gate de acesso + CRUD/captura (integração DB).

- Gate: os endpoints de Partner são superadmin-only (sem token → 401/403, nunca 404/200).
- Integração (Postgres, como o CI): cadastro de Partner, código único, captura
  não-bloqueante no /register, atribuição manual e persistência da origem.
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.partner import Partner

anon_client = TestClient(app)

# ── Gate (sem DB) ─────────────────────────────────────────────────────────────

PARTNER_READ = ["/api/v1/admin/partners"]
_UUID = "00000000-0000-0000-0000-000000000000"
PARTNER_MUTATIONS = [
    ("post", "/api/v1/admin/partners", {"name": "X", "code": "XPTO"}),
    ("patch", f"/api/v1/admin/partners/{_UUID}", {"name": "Y"}),
    ("post", f"/api/v1/admin/partners/{_UUID}/active", {"is_active": False}),
    ("post", f"/api/v1/admin/tenants/{_UUID}/partner", {"partner_id": None}),
]


def test_partner_endpoints_registrados():
    for path in PARTNER_READ:
        assert anon_client.get(path).status_code != 404, f"{path} não registrado"


def test_partner_leitura_exige_superadmin():
    for path in PARTNER_READ:
        assert anon_client.get(path).status_code in (401, 403)


def test_partner_mutacoes_exigem_superadmin():
    for method, path, body in PARTNER_MUTATIONS:
        resp = getattr(anon_client, method)(path, json=body)
        assert resp.status_code in (401, 403), f"{method} {path} veio {resp.status_code}"


# ── Integração DB (Postgres, igual ao CI) ─────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")


def _pg_available() -> bool:
    try:
        eng = create_engine(DATABASE_URL)
        with eng.connect():
            return True
    except Exception:
        return False


pytestmark_db = pytest.mark.skipif(not _pg_available(), reason="Postgres indisponível (roda no CI)")

engine = create_engine(DATABASE_URL) if _pg_available() else None
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) if engine else None


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
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="superadmin")
def superadmin_fixture(session):
    from app.api.deps import get_current_user

    tenant = Tenant(name="Admin Tenant", slug=f"admin-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    admin = User(
        tenant_id=tenant.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@tribultz.com.br",
        full_name="Super Admin",
        password_hash=get_password_hash("x"),
        role="superadmin",
        email_verified=True,
    )
    session.add(admin)
    session.flush()

    def override():
        return admin

    app.dependency_overrides[get_current_user] = override
    yield admin
    app.dependency_overrides.pop(get_current_user, None)


@pytestmark_db
def test_crud_partner_e_codigo_unico(client, superadmin):
    code = f"KATIA{uuid.uuid4().hex[:4].upper()}"
    # criar
    r = client.post("/api/v1/admin/partners", json={"type": "lawyer", "name": "Kátia Advogados", "code": code.lower()})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["code"] == code  # normalizado para uppercase
    assert r.json()["status"] == "active"
    # código duplicado → 409
    assert client.post("/api/v1/admin/partners", json={"name": "Outro", "code": code}).status_code == 409
    # código inválido → 400
    assert client.post("/api/v1/admin/partners", json={"name": "Z", "code": "a b!"}).status_code == 400
    # tipo inválido → 400
    assert client.post("/api/v1/admin/partners", json={"name": "Z", "code": "ZZZ123", "type": "banco"}).status_code == 400
    # editar
    r = client.patch(f"/api/v1/admin/partners/{pid}", json={"name": "Kátia & Associados"})
    assert r.status_code == 200 and r.json()["name"] == "Kátia & Associados"
    # desativar (nunca apagar)
    r = client.post(f"/api/v1/admin/partners/{pid}/active", json={"is_active": False})
    assert r.status_code == 200 and r.json()["status"] == "inactive"


@pytestmark_db
def test_atribuicao_manual_e_filtro(client, superadmin, session):
    partner = Partner(type="accountant", name="INSI", code=f"INSI{uuid.uuid4().hex[:4].upper()}")
    tenant = Tenant(name="Empresa Forms", slug=f"cnpj-{uuid.uuid4().hex[:12]}")
    session.add_all([partner, tenant])
    session.flush()
    # atribuição manual (caso Microsoft Forms)
    r = client.post(f"/api/v1/admin/tenants/{tenant.id}/partner", json={"partner_id": str(partner.id)})
    assert r.status_code == 200 and r.json()["partner_id"] == str(partner.id)
    # a origem aparece no /admin/tenants e o filtro por partner funciona
    r = client.get(f"/api/v1/admin/tenants?partner_id={partner.id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(it["id"] == str(tenant.id) and it["partner_name"] == "INSI" for it in items)
