"""Compliance — risk-patterns (#442).

Gap 4 vs. TOTVS (Inteligência Fiscal by IOB): agregação de findings por
regra/severidade num período, cruzando documentos em vez de validar 1:1.
Testa a query real (jsonb_array_elements) contra Postgres de verdade — mock
de `db.execute()` não valida se o SQL está correto.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.models.auth import Tenant, User
from app.models.jobs import Job
from app.routers.compliance import get_risk_patterns

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")


def _pg_available() -> bool:
    try:
        with create_engine(DATABASE_URL).connect():
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_available(), reason="Postgres indisponível (roda no CI)")

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


def _tenant_and_user(session) -> tuple[Tenant, User]:
    tenant = Tenant(name="Empresa Teste", slug=f"t-{uuid.uuid4().hex[:10]}")
    session.add(tenant)
    session.flush()
    user = User(
        tenant_id=tenant.id, email=f"{uuid.uuid4().hex[:8]}@example.com", full_name="Teste",
        password_hash=get_password_hash("x"), email_verified=True,
    )
    session.add(user)
    session.flush()
    return tenant, user


def _job(tenant_id, job_type: str, findings: list[dict], days_ago: int) -> Job:
    job = Job(
        tenant_id=tenant_id,
        job_type=job_type,
        status="SUCCESS" if not findings else "FAIL",
        result={"findings": findings, "fatals": sum(1 for f in findings if f["severity"] == "FATAL"), "alerts": 0},
        created_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
    )
    return job


def _finding(rule_id: str, severity: str) -> dict:
    return {
        "id": f"F_{uuid.uuid4().hex[:6]}", "rule_id": rule_id, "severity": severity,
        "title": "t", "where": {"field": "x"}, "recommendation": "r", "evidence_ids": [],
    }


def test_top_rules_agrega_por_regra_e_severidade(session):
    tenant, user = _tenant_and_user(session)
    session.add_all([
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("CLASSTRIB_CST_COMPAT", "FATAL")] * 3, days_ago=1),
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("CLASSTRIB_CST_COMPAT", "FATAL"), _finding("CST_VALID", "WARNING")], days_ago=2),
    ])
    session.flush()

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user)

    top = {(r["rule_id"], r["severity"]): r["count"] for r in result["top_rules"]}
    assert top[("CLASSTRIB_CST_COMPAT", "FATAL")] == 4
    assert top[("CST_VALID", "WARNING")] == 1


def test_janela_de_dias_exclui_jobs_fora_do_periodo(session):
    tenant, user = _tenant_and_user(session)
    session.add_all([
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("CLASSTRIB_CST_COMPAT", "FATAL")], days_ago=5),
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("CLASSTRIB_CST_COMPAT", "FATAL")], days_ago=45),
    ])
    session.flush()

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user)

    top = {(r["rule_id"], r["severity"]): r["count"] for r in result["top_rules"]}
    assert top[("CLASSTRIB_CST_COMPAT", "FATAL")] == 1


def test_isolamento_entre_tenants(session):
    tenant_a, user_a = _tenant_and_user(session)
    tenant_b, _user_b = _tenant_and_user(session)
    session.add_all([
        _job(tenant_a.id, "task_a_validate_cbs_ibs", [_finding("RULE_A", "FATAL")], days_ago=1),
        _job(tenant_b.id, "task_a_validate_cbs_ibs", [_finding("RULE_A", "FATAL")] * 10, days_ago=1),
    ])
    session.flush()

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user_a)

    top = {(r["rule_id"], r["severity"]): r["count"] for r in result["top_rules"]}
    assert top[("RULE_A", "FATAL")] == 1  # não vaza o volume do tenant B


def test_daily_trend_conta_por_severidade(session):
    tenant, user = _tenant_and_user(session)
    session.add_all([
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("A", "FATAL"), _finding("B", "WARNING")], days_ago=0),
        _job(tenant.id, "task_a_validate_cbs_ibs", [_finding("A", "ALERT")], days_ago=0),
    ])
    session.flush()

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user)

    today = [d for d in result["daily_trend"] if d["date"] == datetime.now(timezone.utc).date().isoformat()]
    assert len(today) == 1
    assert today[0] == {"date": today[0]["date"], "fatal": 1, "warning": 1, "alert": 1}


def test_sped_validation_fora_do_escopo_nao_quebra(session):
    # SPED guarda achados em result.produtos (formato diferente) — o filtro
    # job_type já exclui esse tipo, não deve aparecer nem quebrar a query.
    tenant, user = _tenant_and_user(session)
    job = Job(
        tenant_id=tenant.id, job_type="sped_validation", status="SUCCESS",
        result={"produtos": [{"ncm": "1234", "status": "ok"}]},
        created_at=datetime.now(timezone.utc),
    )
    session.add(job)
    session.flush()

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user)

    assert result["top_rules"] == []


def test_sem_dados_retorna_vazio(session):
    _tenant, user = _tenant_and_user(session)

    result = get_risk_patterns(days=30, top_n=10, db=session, current_user=user)

    assert result == {"period_days": 30, "top_rules": [], "daily_trend": []}
