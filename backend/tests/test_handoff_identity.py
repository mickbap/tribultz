"""Round 4 §1: os 9 cenários de identidade da DEC-5 (campanha QA).

Resolução determinística de pessoa — igualdade exata pós-normalização, sem
matching probabilístico. DB real (Postgres migrado) com rollback por teste,
padrão de test_support_tenancy.py. Dados 100% sintéticos.
"""

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.auth import Tenant
from app.services.handoff.identity import (
    normalize_email,
    normalize_linkedin,
    person_protected,
    resolve_person,
)

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
    tenant = Tenant(name=f"Tenant QA {uuid.uuid4().hex[:6]}", slug=f"tenant-qa-{uuid.uuid4()}")
    session.add(tenant)
    session.flush()
    return tenant.id


EMAIL = "pessoa.sintetica@example.test"
LINKEDIN = "https://www.linkedin.com/in/Pessoa-Sintetica-QA/"


def test_normalizacao_email():
    assert normalize_email("  Pessoa.Sintetica@Example.TEST ") == EMAIL
    assert normalize_email("sem-arroba") is None
    assert normalize_email("   ") is None
    assert normalize_email(None) is None


def test_cenario_6_linkedin_igual_em_formatos_diferentes():
    canonical = "in/pessoa-sintetica-qa"
    assert normalize_linkedin("https://www.LinkedIn.com/in/Pessoa-Sintetica-QA/?utm=x") == canonical
    assert normalize_linkedin("linkedin.com/in/pessoa-sintetica-qa") == canonical
    assert normalize_linkedin("in/pessoa-sintetica-qa/") == canonical
    assert normalize_linkedin("pessoa-sintetica-qa") == canonical  # handle nu → /in/<handle>
    assert normalize_linkedin("br.linkedin.com/in/pessoa-sintetica-qa") == canonical


def test_cenario_1_mesma_pessoa_mesmo_dado_resolve_uma_vez(session, tenant_id):
    r1 = resolve_person(session, tenant_id, EMAIL, None)
    r2 = resolve_person(session, tenant_id, EMAIL, None)
    assert r1.created is True and r2.created is False
    assert r1.identity.id == r2.identity.id  # type: ignore[misc]


def test_cenario_4_mesmo_linkedin_email_diferente_nao_sobrescreve(session, tenant_id):
    r1 = resolve_person(session, tenant_id, EMAIL, LINKEDIN)
    r2 = resolve_person(session, tenant_id, "outro.email@example.test", LINKEDIN)
    assert r2.identity.id == r1.identity.id  # LinkedIn exato identifica a pessoa  # type: ignore[misc]
    assert r2.identity.email_normalized == EMAIL  # chave existente jamais sobrescrita  # type: ignore[misc]


def test_cenario_5_mesmo_email_linkedin_ausente(session, tenant_id):
    r1 = resolve_person(session, tenant_id, EMAIL, LINKEDIN)
    r2 = resolve_person(session, tenant_id, EMAIL, None)
    assert r2.identity.id == r1.identity.id  # type: ignore[misc]


def test_enriquecimento_deterministico_preenche_chave_vazia(session, tenant_id):
    r1 = resolve_person(session, tenant_id, EMAIL, None)
    assert r1.identity.linkedin_normalized is None  # type: ignore[misc]
    r2 = resolve_person(session, tenant_id, EMAIL, LINKEDIN)
    assert r2.identity.id == r1.identity.id  # type: ignore[misc]
    assert r2.identity.linkedin_normalized == "in/pessoa-sintetica-qa"  # type: ignore[misc]


def test_cenario_7_identidade_parcial_nao_resolve(session, tenant_id):
    r = resolve_person(session, tenant_id, None, None)
    assert r.identity is None and r.conflict is False


def test_cenario_8_identidade_conflitante_sem_merge(session, tenant_id):
    a = resolve_person(session, tenant_id, "pessoa.a@example.test", "in/pessoa-a-qa").identity
    b = resolve_person(session, tenant_id, "pessoa.b@example.test", "in/pessoa-b-qa").identity

    r = resolve_person(session, tenant_id, "pessoa.a@example.test", "in/pessoa-b-qa")
    assert r.conflict is True and r.identity is None
    assert {m.id for m in r.matched} == {a.id, b.id}  # type: ignore[misc]
    # nada foi mesclado nem alterado
    session.refresh(a), session.refresh(b)
    assert a.email_normalized == "pessoa.a@example.test"  # type: ignore[misc]
    assert a.linkedin_normalized == "in/pessoa-a-qa"  # type: ignore[misc]
    assert b.email_normalized == "pessoa.b@example.test"  # type: ignore[misc]
    assert b.linkedin_normalized == "in/pessoa-b-qa"  # type: ignore[misc]


def test_cenario_9_dado_compartilhado_colapsa_por_desenho(session, tenant_id):
    """Duas pessoas legitimamente distintas com o MESMO e-mail colapsam na mesma
    identidade — comportamento explícito e documentado (mesma semântica do
    Attio, onde e-mail é chave única). Modo de falha conservador: bloqueia
    outbound a mais, nunca a menos; separação é curadoria humana."""
    r1 = resolve_person(session, tenant_id, "caixa.compartilhada@example.test", None,
                        display_name="Pessoa Um [QA]")
    r2 = resolve_person(session, tenant_id, "caixa.compartilhada@example.test", None,
                        display_name="Pessoa Dois [QA]")
    assert r2.identity.id == r1.identity.id  # type: ignore[misc]
    assert r2.created is False


def test_protecao_por_pessoa_sem_vinculos_e_falsa(session, tenant_id):
    r = resolve_person(session, tenant_id, EMAIL, None)
    assert person_protected(session, tenant_id, [r.identity.id]) is False  # type: ignore[arg-type, misc]


def test_isolamento_entre_tenants(session, tenant_id):
    """Mesmo dado em tenants distintos = pessoas distintas (Round 4 §11)."""
    other = Tenant(name=f"Tenant QA2 {uuid.uuid4().hex[:6]}", slug=f"tenant-qa2-{uuid.uuid4()}")
    session.add(other)
    session.flush()
    r1 = resolve_person(session, tenant_id, EMAIL, None)
    r2 = resolve_person(session, other.id, EMAIL, None)  # type: ignore[arg-type]
    assert r1.identity.id != r2.identity.id  # type: ignore[misc]
