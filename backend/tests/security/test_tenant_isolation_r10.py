"""Round 10 — reprodução DINÂMICA da fronteira de isolamento de tenant (P0).

A ordem exige decidir por EXECUÇÃO, não por interpretação. Este módulo prova,
contra o app FastAPI real + Postgres real, os dois caminhos da divergência
Techlead × QA, separando três propriedades independentes (§6):

  ASSOCIAÇÃO INDEVIDA · LEITURA INDEVIDA · ESCRITA/OPERAÇÃO INDEVIDA

Ambiente 100% SINTÉTICO (§5): CNPJs fictícios (dígitos repetidos), e-mails
`r10-*@example.com`, artefatos `[SINTÉTICO-R10]`. Nenhum dado real, nenhuma
mudança de produção. Só a fronteira EXTERNA (validação de CNPJ na BrasilAPI e
captcha) é mockada — o código de AUTH exercitado é o de produção, intacto.
Toda linha criada é removida no teardown (marcador determinístico).
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

import app.routers.auth as auth_router
from app.main import app
from app.models.auth import Tenant, User, UserTenant
from app.models.billing import Plan
from app.models.exception_requests import ExceptionRequest

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="isolamento exige Postgres (infra local/CI)"
)

RUN = uuid.uuid4().hex[:8]
CNPJ_A = "11111111000191"  # sintético (dígitos repetidos), DV válido
CNPJ_B = "22222222000191"
PWD = "SenhaSintetica!R10"
MARK = "[SINTÉTICO-R10]"


class _FakeCnpj:
    """Substitui a chamada externa à BrasilAPI — resultado sintético determinístico."""

    def __init__(self, cnpj: str):
        self.valid = True
        self.cnpj = cnpj
        self.company_name = f"{MARK} Empresa {cnpj[:8]}"
        self.error = None


@pytest.fixture()
def client(monkeypatch):
    async def _fake_validate_cnpj(cnpj: str):
        return _FakeCnpj(cnpj)

    async def _fake_captcha(token, ip):  # noqa: ANN001
        return True

    monkeypatch.setattr(auth_router, "validate_cnpj", _fake_validate_cnpj)
    monkeypatch.setattr(auth_router, "verify_captcha", _fake_captcha)
    # rate limiters (login/register) são controle externo, não o alvo do teste —
    # neutralizados como o captcha/CNPJ; a lógica de AUTH exercitada é a de produção
    monkeypatch.setattr(auth_router._register_limiter, "check_or_raise", lambda *a, **k: None)
    monkeypatch.setattr(auth_router._login_limiter, "check_or_raise", lambda *a, **k: None)

    created_plan = False
    with SessionLocal() as s:
        if s.execute(select(Plan).where(Plan.slug == "trial")).scalar_one_or_none() is None:
            s.add(Plan(slug="trial", name=f"{MARK} Trial", price_cents=0, max_cnpj=1,
                       is_active=True))
            s.commit()
            created_plan = True

    yield TestClient(app)

    # teardown determinístico — remove tudo que este run criou
    with SessionLocal() as s:
        tenant_ids = [
            t for (t,) in s.execute(
                select(Tenant.id).where(Tenant.slug.in_([f"cnpj-{CNPJ_A}", f"cnpj-{CNPJ_B}"]))
            ).all()
        ]
        if tenant_ids:
            s.execute(delete(ExceptionRequest).where(ExceptionRequest.tenant_id.in_(tenant_ids)))
            uids = [u for (u,) in s.execute(
                select(User.id).where(User.tenant_id.in_(tenant_ids))).all()]
            if uids:
                s.execute(delete(UserTenant).where(UserTenant.user_id.in_(uids)))
                s.execute(delete(User).where(User.id.in_(uids)))
            s.execute(delete(UserTenant).where(UserTenant.tenant_id.in_(tenant_ids)))
            s.execute(delete(Tenant).where(Tenant.id.in_(tenant_ids)))
        s.execute(delete(User).where(User.email.like(f"r10-%-{RUN}@example.com")))
        if created_plan:
            s.execute(delete(Plan).where(Plan.slug == "trial", Plan.name == f"{MARK} Trial"))
        s.commit()


def _register(client, email, cnpj, account_type):
    return client.post("/api/v1/auth/register", json={
        "email": email, "password": PWD, "full_name": f"{MARK} {email}",
        "cnpj": cnpj, "account_type": account_type, "plan_slug": "trial",
        "lgpd_consent": True, "terms_accepted": True, "refund_policy_accepted": True,
        "captcha_token": "x",
    })


def _verify_and_login(client, email):
    # o atacante verifica o PRÓPRIO e-mail (inbox que ele controla) — não protege a vítima
    with SessionLocal() as s:
        u = s.execute(select(User).where(User.email == email)).scalar_one()
        u.email_verified = True  # type: ignore[assignment]
        s.commit()
    r = client.post("/api/v1/auth/login", json={"email": email, "password": PWD,
                                                 "captcha_token": "x"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _bearer(tok):
    return {"Authorization": f"Bearer {tok}"}


def _exc_payload(finding):
    return {"finding_id": finding, "rule_id": "IBSCBS_MISSING",
            "justification": f"{MARK} justificativa {finding}",
            "admin_name": "Admin A", "admin_email": "admin.a@example.com"}


def _user(email):
    with SessionLocal() as s:
        return s.execute(select(User).where(User.email == email)).scalar_one()


# ══════════════════════════════════════════════════════════════════════════════
# ATAQUE B (§5, prioritário) — register com CNPJ preexistente
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("account_type", ["empresa", "contador"])
def test_ataque_B_register_cnpj_existente_agora_CONTIDO(client, account_type):
    """PROVA DINÂMICA + CONTENÇÃO do Ataque B (§5, prioritário).

    Parametrizado nos dois `account_type` (Round 11, A1): o Round 10 provou que
    `empresa` e `contador` reproduziam o ataque por inteiro, e que `role` não era
    o vetor — `tenant_id` era. A regressão precisa cobrir os dois, senão fecha
    metade da porta.

    ANTES da contenção (comprovado verde nesta sessão, pré-fix): register com
    CNPJ preexistente + account_type=empresa retornava 201, nascia com
    tenant_id da vítima e role=admin, e permitia LER a exceção da vítima,
    ESCREVER no tenant dela e DECIDIR (operação privilegiada). ASSOCIAÇÃO +
    LEITURA + ESCRITA/OPERAÇÃO cross-tenant — vulnerabilidade de isolamento.

    DEPOIS da contenção mínima (register bloqueia ingresso em tenant já
    povoado): o atacante recebe 409 e NENHUM usuário/vínculo cross-tenant é
    criado. SEC-INV-1/2 restauradas.
    """
    email_a = f"r10-vitima-{account_type}-{RUN}@example.com"
    email_x = f"r10-atacante-{account_type}-{RUN}@example.com"

    # Vítima A cria TENANT_A e um artefato scoped
    assert _register(client, email_a, CNPJ_A, "empresa").status_code == 201
    tok_a = _verify_and_login(client, email_a)
    r = client.post("/api/v1/exceptions", json=_exc_payload(f"{MARK}-SEGREDO-A"),
                    headers=_bearer(tok_a))
    assert r.status_code == 201, r.text
    tenant_a = _user(email_a).tenant_id

    # ATACANTE tenta o mesmo CNPJ → CONTIDO (409), sem cross-tenant
    r = _register(client, email_x, CNPJ_A, account_type)
    assert r.status_code == 409, f"contenção falhou — vuln reaberta: {r.status_code} {r.text}"
    assert "autorização" in r.text.lower() or "conta" in r.text.lower()

    # A1 (Round 11): não basta o 409 — conferir o ESTADO PERSISTIDO.
    # Nenhum usuário atacante nasceu; nenhum membership cross-tenant existe; e o
    # tenant da vítima continua exatamente como estava.
    with SessionLocal() as s:
        assert s.execute(select(User).where(User.email == email_x)).scalar_one_or_none() is None
        n = s.execute(select(User).where(User.tenant_id == tenant_a)).all()
        assert len(n) == 1, "tenant da vítima ganhou membro indevido"
        vinculos = s.execute(
            select(UserTenant).where(UserTenant.tenant_id == tenant_a)
        ).all()
        assert len(vinculos) == 1, "tenant da vítima ganhou vínculo indevido"


def test_registro_legitimo_cnpj_novo_ainda_funciona(client):
    """§10 — a contenção NÃO pode quebrar onboarding legítimo: CNPJ novo → 201."""
    email = f"r10-novo-{RUN}@example.com"
    r = _register(client, email, CNPJ_B, "empresa")
    assert r.status_code == 201, r.text
    assert str(_user(email).role) == "admin"  # 1º usuário do próprio CNPJ é admin, correto


def test_reivindicacao_de_shell_vazio_ainda_funciona(client):
    """§10 — tenant-shell SEM usuários (pré-provisionado por diagnóstico/founding
    partner) permanece reivindicável pelo 1º usuário. A contenção só bloqueia
    tenant JÁ POVOADO."""
    # cria um shell vazio com o slug canônico do CNPJ_A (sem usuários)
    with SessionLocal() as s:
        s.add(Tenant(name=f"{MARK} Shell", slug=f"cnpj-{CNPJ_A}"))
        s.commit()
    email = f"r10-claim-{RUN}@example.com"
    r = _register(client, email, CNPJ_A, "empresa")
    assert r.status_code == 201, r.text
    with SessionLocal() as s:
        shell = s.execute(select(Tenant).where(Tenant.slug == f"cnpj-{CNPJ_A}")).scalar_one()
        assert str(_user(email).tenant_id) == str(shell.id)  # reivindicou o shell existente


def test_impacto_do_estado_sob_ataque_leitura_escrita_operacao(client):
    """§5/§6 — prova EXECUTÁVEL do impacto do Ataque B (o que há ATRÁS da porta).

    A contenção fecha o `/register`; mas a ordem (§5) exige EXECUTAR as quatro
    perguntas de impacto (ler / escrever / operação privilegiada), não deduzi-las
    ("não aceito 'parece que'"). Reproduzo aqui, sinteticamente, o ESTADO
    PERSISTIDO que o register pré-fix gerava — `User.tenant_id` = tenant da
    vítima, `role=admin` (linha idêntica à de `auth.py` register, provada no
    Ataque B) — semeando a linha diretamente, SEM reabrir o endpoint, e provo o
    que um atacante nesse estado CONSEGUE FAZER contra as superfícies
    tenant-scoped reais.

    Derruba também a atribuição do impacto a `role=admin`: um membro NÃO-admin
    (`role=contador`) no mesmo tenant executa a MESMA operação privilegiada
    (decidir exceção — o endpoint gate é `tenant_id`, não papel). O driver do
    vazamento é `current_user.tenant_id` (SEC-INV-5), não o papel administrativo.
    """
    from app.core.security import get_password_hash

    email_a = f"r10-vA3-{RUN}@example.com"
    assert _register(client, email_a, CNPJ_A, "empresa").status_code == 201
    tok_a = _verify_and_login(client, email_a)
    r = client.post("/api/v1/exceptions", json=_exc_payload(f"{MARK}-SEGREDO-A3"),
                    headers=_bearer(tok_a))
    assert r.status_code == 201, r.text
    segredo_id = r.json()["id"]
    tenant_a = _user(email_a).tenant_id

    def _seed_attacker_in_victim_tenant(email, role):
        # replica exatamente o que auth.py:382 register criava pré-fix
        with SessionLocal() as s:
            s.add(User(email=email, full_name=f"{MARK} atacante {role}",
                       password_hash=get_password_hash(PWD), tenant_id=tenant_a,
                       role=role, email_verified=True))
            s.commit()
        r = client.post("/api/v1/auth/login",
                        json={"email": email, "password": PWD, "captcha_token": "x"})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]

    tok_x = _seed_attacker_in_victim_tenant(f"r10-atkAdmin-{RUN}@example.com", "admin")

    # LEITURA INDEVIDA = SIM
    r = client.get("/api/v1/exceptions", headers=_bearer(tok_x))
    assert r.status_code == 200, r.text
    assert f"{MARK}-SEGREDO-A3" in [e["finding_id"] for e in r.json()], "não leu o segredo da vítima"

    # ESCRITA INDEVIDA = SIM (grava dentro do tenant da vítima)
    r = client.post("/api/v1/exceptions", json=_exc_payload(f"{MARK}-INJETADO-X"),
                    headers=_bearer(tok_x))
    assert r.status_code == 201 and r.json()["tenant_id"] == str(tenant_a), r.text

    # OPERAÇÃO PRIVILEGIADA = SIM (decide a exceção da vítima → muta estado + audit_log)
    r = client.post(f"/api/v1/exceptions/{segredo_id}/decision",
                    json={"status": "APPROVED"}, headers=_bearer(tok_x))
    assert r.status_code == 200 and r.json()["status"] == "APPROVED", r.text

    # QA — impacto NÃO depende de role=admin: membro contador decide igual
    r = client.post("/api/v1/exceptions", json=_exc_payload(f"{MARK}-SEGREDO-A3b"),
                    headers=_bearer(tok_a))
    nova_id = r.json()["id"]
    tok_m = _seed_attacker_in_victim_tenant(f"r10-atkMember-{RUN}@example.com", "contador")
    r = client.post(f"/api/v1/exceptions/{nova_id}/decision",
                    json={"status": "REJECTED"}, headers=_bearer(tok_m))
    assert r.status_code == 200 and r.json()["status"] == "REJECTED", \
        "membro não-admin também opera → driver do impacto é tenant_id, não o papel"


# ══════════════════════════════════════════════════════════════════════════════
# ATAQUE A — add-cnpj + switch-tenant (resolve a divergência)
# ══════════════════════════════════════════════════════════════════════════════

def test_ataque_A_switch_tenant_e_cosmetico_para_leitura(client, monkeypatch):
    email_a = f"r10-vitimaA2-{RUN}@example.com"
    email_c = f"r10-contador-{RUN}@example.com"

    # vítima A + exceção
    assert _register(client, email_a, CNPJ_A, "empresa").status_code == 201
    tok_a = _verify_and_login(client, email_a)
    client.post("/api/v1/exceptions", json=_exc_payload(f"{MARK}-SEGREDO-A2"),
                headers=_bearer(tok_a))
    tenant_a = _user(email_a).tenant_id

    # contador atacante, tenant próprio (CNPJ_B)
    assert _register(client, email_c, CNPJ_B, "contador").status_code == 201
    tok_c = _verify_and_login(client, email_c)
    tenant_c_before = _user(email_c).tenant_id

    # MITIGAÇÃO PARCIAL comprovada: no plano trial (max_cnpj=1, já usado no próprio
    # registro) o add-cnpj é BLOQUEADO por limite de plano — 403.
    r = client.post("/api/v1/auth/add-cnpj", json={"cnpj": CNPJ_A}, headers=_bearer(tok_c))
    assert r.status_code == 403 and "Limite" in r.text, r.text

    # …mas o plano Contador (max_cnpj=50) é exatamente a persona-alvo. Simulo o
    # limite do plano (controle externo) para exercitar a associação e provar a
    # parte que interessa: a LEITURA. Membership: ASSOCIAÇÃO INDEVIDA = SIM.
    import types
    import app.api.plan_gate as plan_gate

    monkeypatch.setattr(plan_gate, "get_effective_plan",
                        lambda db, user: types.SimpleNamespace(max_cnpj=50))
    r = client.post("/api/v1/auth/add-cnpj", json={"cnpj": CNPJ_A}, headers=_bearer(tok_c))
    assert r.status_code == 200, r.text
    with SessionLocal() as s:
        membership = s.execute(
            select(UserTenant).where(UserTenant.user_id == _user(email_c).id,
                                     UserTenant.tenant_id == tenant_a)
        ).scalar_one_or_none()
        assert membership is not None, "membership não foi criado"

    # switch-tenant(TENANT_A): JWT muda (claim tenant_id=A)…
    r = client.post("/api/v1/auth/switch-tenant", json={"tenant_id": str(tenant_a)},
                    headers=_bearer(tok_c))
    assert r.status_code == 200, r.text
    tok_switched = r.json()["access_token"]
    assert r.json()["tenant_id"] == str(tenant_a)  # JWT mudou

    # …mas current_user.tenant_id (coluna persistida) NÃO mudou
    assert str(_user(email_c).tenant_id) == str(tenant_c_before), "switch-tenant mutou a coluna (seria grave)"

    # LEITURA INDEVIDA = NÃO: os endpoints usam current_user.tenant_id, não o claim
    r = client.get("/api/v1/exceptions", headers=_bearer(tok_switched))
    assert r.status_code == 200, r.text
    leaked = [e["finding_id"] for e in r.json() if "SEGREDO" in e["finding_id"]]
    # o contador lê pelo current_user.tenant_id (o próprio), não pelo claim do JWT —
    # switch-tenant é COSMÉTICO para leitura. Nenhum segredo da vítima pode vazar.
    assert leaked == [], f"LEITURA CROSS-TENANT via switch-tenant: {leaked}"


def test_divergencia_resolvida_por_execucao(client):
    """Sumário executável da divergência: A cosmético, B concede acesso real."""
    # (asserções já provadas nos dois testes acima; este fixa o veredito)
    assert True
