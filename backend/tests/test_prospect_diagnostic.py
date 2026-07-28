"""Prospect Diagnostic (Escopo A, plano de aquisição comercial, 2026-07-28).

- Gate: endpoints são superadmin-only (sem token → 401/403, nunca 404/200).
- Integração (Postgres, como o CI): upload de XMLs, geração de PDF, listagem.
- Atribuição no /register: captura não-bloqueante de ?diag= (mesmo padrão do
  Partner/RFC-0025, testado diretamente contra o helper — sem HTTP, mesmo
  padrão usado para o resto da suíte de auth).
"""

import os
import uuid
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models.auth import Tenant, User
from app.models.prospect_diagnostic import ProspectDiagnostic

anon_client = TestClient(app)

# ── Gate (sem DB) ─────────────────────────────────────────────────────────────

PROSPECT_READ = ["/api/v1/admin/prospect-diagnostics"]


def test_prospect_diagnostic_endpoints_registrados():
    for path in PROSPECT_READ:
        assert anon_client.get(path).status_code != 404, f"{path} não registrado"


def test_prospect_diagnostic_leitura_exige_superadmin():
    for path in PROSPECT_READ:
        assert anon_client.get(path).status_code in (401, 403)


def test_prospect_diagnostic_criacao_exige_superadmin():
    resp = anon_client.post(
        "/api/v1/admin/prospect-diagnostics",
        data={"office_name": "X"},
        files=[("files", ("nota.xml", b"<a/>", "application/xml"))],
    )
    assert resp.status_code in (401, 403)


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


VALID_NFE_XML = """<?xml version="1.0"?>
<nfeProc>
  <NFe>
    <infNFe>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod>
          <NCM>84713012</NCM>
          <CEST>2106300</CEST>
          <CFOP>5102</CFOP>
        </prod>
        <imposto>
          <IBSCBS>
            <CST>000</CST>
            <cClassTrib>100001</cClassTrib>
            <gIBSCBS>
              <vBC>1000.00</vBC>
              <pCBS>0.0010</pCBS>
              <vCBS>1.00</vCBS>
              <pIBSUF>0.0050</pIBSUF>
              <vIBSUF>5.00</vIBSUF>
              <pIBSMun>0.0040</pIBSMun>
              <vIBSMun>4.00</vIBSMun>
              <vIBS>9.00</vIBS>
            </gIBSCBS>
          </IBSCBS>
        </imposto>
      </det>
      <total>
        <IBSCBSTot>
          <vCBS>1.00</vCBS>
          <vIBS>9.00</vIBS>
        </IBSCBSTot>
      </total>
    </infNFe>
  </NFe>
</nfeProc>
"""

INVALID_NFE_XML_MISSING_CST = """<?xml version="1.0"?>
<nfeProc>
  <NFe>
    <infNFe>
      <emit><CNPJ>12345678000195</CNPJ></emit>
      <det nItem="1">
        <prod><NCM>84713012</NCM><CEST>2106300</CEST></prod>
        <imposto>
          <IBSCBS>
            <CST>999</CST>
            <cClassTrib>100001</cClassTrib>
          </IBSCBS>
        </imposto>
      </det>
      <total></total>
    </infNFe>
  </NFe>
</nfeProc>
"""


@pytestmark_db
def test_gera_diagnostico_com_xmls_mistos(client, superadmin):
    resp = client.post(
        "/api/v1/admin/prospect-diagnostics",
        data={"office_name": "Contabilidade Teste Ltda"},
        files=[
            ("files", ("nota_ok.xml", VALID_NFE_XML.encode("utf-8"), "application/xml")),
            ("files", ("nota_erro.xml", INVALID_NFE_XML_MISSING_CST.encode("utf-8"), "application/xml")),
        ],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["office_name"] == "Contabilidade Teste Ltda"
    assert body["invoice_count"] == 2
    assert body["rejected_count"] == 1
    assert body["download_url"]
    assert body["id"] in body["trial_url"]
    statuses = {inv["label"]: inv["status"] for inv in body["invoices"]}
    assert statuses["nota_ok.xml"] == "PASS"
    assert statuses["nota_erro.xml"] == "FAIL"


@pytestmark_db
def test_diagnostico_persistido_e_listado(client, superadmin, session):
    resp = client.post(
        "/api/v1/admin/prospect-diagnostics",
        data={"office_name": "Escritório Listagem"},
        files=[("files", ("nota.xml", VALID_NFE_XML.encode("utf-8"), "application/xml"))],
    )
    assert resp.status_code == 200
    diag_id = resp.json()["id"]

    row = session.get(ProspectDiagnostic, uuid.UUID(diag_id))
    assert row is not None
    assert row.storage_key is not None
    assert row.created_by_user_id == superadmin.id

    listed = client.get("/api/v1/admin/prospect-diagnostics")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert diag_id in ids


@pytestmark_db
def test_rejeita_sem_arquivos_ou_sem_nome(client, superadmin):
    r1 = client.post("/api/v1/admin/prospect-diagnostics", data={"office_name": "   "}, files=[("files", ("a.xml", b"<a/>", "application/xml"))])
    assert r1.status_code == 400, r1.text
    r2 = client.post("/api/v1/admin/prospect-diagnostics", data={"office_name": "X"}, files=[])
    assert r2.status_code in (400, 422)


# ── Atribuição no /register (?diag=) ─────────────────────────────────────────

@pytestmark_db
def test_attach_prospect_diagnostic_vincula_tenant(session):
    from app.routers.auth import _attach_prospect_diagnostic

    tenant_admin = Tenant(name="Admin", slug=f"admin-{uuid.uuid4().hex[:8]}")
    session.add(tenant_admin)
    session.flush()
    admin_user = User(
        tenant_id=tenant_admin.id, email=f"a-{uuid.uuid4().hex[:8]}@x.com",
        full_name="A", password_hash=get_password_hash("x"), role="superadmin", email_verified=True,
    )
    session.add(admin_user)
    session.flush()

    diagnostic = ProspectDiagnostic(office_name="Prospect X", created_by_user_id=admin_user.id)
    session.add(diagnostic)
    session.flush()

    tenant = Tenant(name="Empresa Nova", slug=f"nova-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()

    _attach_prospect_diagnostic(session, tenant, str(diagnostic.id))
    assert cast(uuid.UUID, tenant.prospect_diagnostic_id) == diagnostic.id


@pytestmark_db
def test_attach_prospect_diagnostic_ignora_id_invalido_sem_bloquear(session):
    from app.routers.auth import _attach_prospect_diagnostic

    tenant = Tenant(name="Empresa Sem Diag", slug=f"semdiag-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()

    _attach_prospect_diagnostic(session, tenant, "não-é-um-uuid")
    assert tenant.prospect_diagnostic_id is None

    _attach_prospect_diagnostic(session, tenant, str(uuid.uuid4()))  # inexistente
    assert tenant.prospect_diagnostic_id is None


@pytestmark_db
def test_attach_prospect_diagnostic_e_permanente(session):
    from app.routers.auth import _attach_prospect_diagnostic

    tenant_admin = Tenant(name="Admin2", slug=f"admin2-{uuid.uuid4().hex[:8]}")
    session.add(tenant_admin)
    session.flush()
    admin_user = User(
        tenant_id=tenant_admin.id, email=f"b-{uuid.uuid4().hex[:8]}@x.com",
        full_name="B", password_hash=get_password_hash("x"), role="superadmin", email_verified=True,
    )
    session.add(admin_user)
    session.flush()

    diag1 = ProspectDiagnostic(office_name="Primeiro", created_by_user_id=admin_user.id)
    diag2 = ProspectDiagnostic(office_name="Segundo", created_by_user_id=admin_user.id)
    session.add_all([diag1, diag2])
    session.flush()

    tenant = Tenant(name="Empresa Fixa", slug=f"fixa-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()

    _attach_prospect_diagnostic(session, tenant, str(diag1.id))
    assert cast(uuid.UUID, tenant.prospect_diagnostic_id) == diag1.id

    _attach_prospect_diagnostic(session, tenant, str(diag2.id))
    assert cast(uuid.UUID, tenant.prospect_diagnostic_id) == diag1.id  # não sobrescreve
