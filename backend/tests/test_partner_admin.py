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
    ("post", f"/api/v1/admin/partners/{_UUID}/account", {"email": "x@x.com", "full_name": "X", "initial_password": "password123"}),
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

# create_engine é lazy (não conecta aqui); a conexão real só acontece nas fixtures
# dos testes não-pulados. Criado incondicionalmente para o tipo não ser Optional.
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
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limiters():
    """Evita 429 em /login entre arquivos de teste (mesmo padrão de test_auth.py)."""
    from app.routers.auth import _login_limiter, _register_limiter, _forgot_limiter

    prefixes = ["ratelimit:login:", "ratelimit:register:", "ratelimit:resend:", "ratelimit:forgot:"]
    for rl in (_login_limiter, _register_limiter, _forgot_limiter):
        rl._memory_store.clear()
    redis_conn = _login_limiter.redis
    if redis_conn is not None:
        for prefix in prefixes:
            redis_conn.delete(f"{prefix}testclient")
            redis_conn.delete(f"{prefix}127.0.0.1")
            redis_conn.delete(f"{prefix}unknown")


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
    assert r.json()["has_account"] is False
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


# ── Cadastro de conta do Partner (RFC-0026, Fase 1) ───────────────────────────
# Mesmo padrão do Founding Partner (_provision_tenant_and_user): admin cria a
# conta com senha inicial — sem convite/e-mail automático (não existe no
# código hoje; ver docs/sprints/2026-07-16_programa_parceiros_fundacao_auth.md).

def _make_partner(session, code_prefix="ACC"):
    partner = Partner(type="accountant", name="Dra. Kátia Pollon", code=f"{code_prefix}{uuid.uuid4().hex[:5].upper()}")
    session.add(partner)
    session.flush()
    return partner


@pytestmark_db
def test_create_partner_account_success(client, superadmin, session):
    from sqlalchemy import select as sa_select

    partner = _make_partner(session)
    email = f"katia-{uuid.uuid4().hex[:6]}@example.com"
    r = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": email, "full_name": "Dra. Kátia Pollon", "initial_password": "senhaforte123"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email"] == email
    assert body["partner_id"] == str(partner.id)

    user = session.execute(sa_select(User).where(User.email == email)).scalar_one()
    assert user.partner_id == partner.id
    assert user.tenant_id is None
    assert user.actor_type == "partner"
    assert user.role == "partner"

    # GET /admin/partners reflete has_account (usado pela UI para decidir
    # se mostra "criar conta" ou "conta já existe").
    listed = client.get("/api/v1/admin/partners").json()["items"]
    assert next(p for p in listed if p["id"] == str(partner.id))["has_account"] is True


@pytestmark_db
def test_create_partner_account_short_password_rejected(client, superadmin, session):
    partner = _make_partner(session, "SHORT")
    r = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": f"x-{uuid.uuid4().hex[:6]}@example.com", "full_name": "X", "initial_password": "1234567"},
    )
    assert r.status_code == 400


@pytestmark_db
def test_create_partner_account_duplicate_email_rejected(client, superadmin, session):
    """E-mail já usado por qualquer ator (tenant ou partner) — login é global por e-mail;
    duas contas com o mesmo e-mail quebrariam o login (scalar_one_or_none)."""
    existing_tenant = Tenant(name="Empresa X", slug=f"empresa-{uuid.uuid4().hex[:8]}")
    session.add(existing_tenant)
    session.flush()
    taken_email = f"taken-{uuid.uuid4().hex[:6]}@example.com"
    session.add(User(
        tenant_id=existing_tenant.id, email=taken_email, full_name="Alguém",
        password_hash=get_password_hash("x"), role="user", email_verified=True,
    ))
    session.flush()

    partner = _make_partner(session, "DUP")
    r = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": taken_email, "full_name": "Dra. Kátia Pollon", "initial_password": "senhaforte123"},
    )
    assert r.status_code == 409


@pytestmark_db
def test_create_partner_account_already_exists_rejected(client, superadmin, session):
    partner = _make_partner(session, "TWICE")
    first_email = f"first-{uuid.uuid4().hex[:6]}@example.com"
    r1 = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": first_email, "full_name": "Dra. Kátia Pollon", "initial_password": "senhaforte123"},
    )
    assert r1.status_code == 201, r1.text

    r2 = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": f"second-{uuid.uuid4().hex[:6]}@example.com", "full_name": "Dra. Kátia Pollon", "initial_password": "senhaforte123"},
    )
    assert r2.status_code == 409


@pytestmark_db
def test_create_partner_account_inactive_partner_rejected(client, superadmin, session):
    partner = _make_partner(session, "INACT")
    partner.status = "inactive"  # type: ignore[assignment]
    session.flush()
    r = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": f"x-{uuid.uuid4().hex[:6]}@example.com", "full_name": "X", "initial_password": "senhaforte123"},
    )
    assert r.status_code == 400


@pytestmark_db
def test_partner_account_can_actually_login(client, superadmin, session):
    """Ponta a ponta: a conta criada aqui usa o mesmo /login de todo mundo."""
    partner = _make_partner(session, "LOGIN")
    email = f"login-{uuid.uuid4().hex[:6]}@example.com"
    r = client.post(
        f"/api/v1/admin/partners/{partner.id}/account",
        json={"email": email, "full_name": "Dra. Kátia Pollon", "initial_password": "senhaforte123"},
    )
    assert r.status_code == 201, r.text

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "senhaforte123"})
    assert login.status_code == 200
    from jose import jwt

    from app.config import settings

    claims = jwt.decode(login.json()["access_token"], settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    assert claims["actor_type"] == "partner"
    assert claims["partner_id"] == str(partner.id)
