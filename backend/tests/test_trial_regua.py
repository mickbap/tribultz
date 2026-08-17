"""Régua de aceite do Trial — 9 itens (#635, L1.5).

A decisão de Produto de 16/08/2026 fixou: 3 dias corridos, 5 validações no
TRIAL INTEIRO (não por mês), TXT sim, PDF/API/dashboard/suporte não, encerrando
no primeiro evento entre D+3 e a 5ª validação.

O que existia antes: três superfícies com números diferentes e um backend que
contava por mês-calendário. Estes testes tratam a decisão como CONTRATO.
"""

from __future__ import annotations

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from app.api.plan_gate import _periodo_de_uso, _trial_expirado, check_usage_limit, increment_usage
from app.data.trial_policy import (
    TRIAL_DURATION_DAYS,
    TRIAL_QUOTA_PERIOD,
    TRIAL_USAGE_PERIOD,
    TRIAL_VALIDATION_QUOTA,
    trial_policy,
)
from app.models.auth import Tenant, User
from app.models.billing import Plan, Subscription, UsageTracking

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


@pytest.fixture
def usuario_trial():
    """Usuário com assinatura em trial válida, e limpeza ao fim."""
    with Session() as db:
        plano = db.execute(select(Plan).where(Plan.slug == "trial")).scalar_one()
        sufixo = uuid.uuid4().hex[:10]
        tenant = Tenant(name=f"t-{sufixo}", slug=f"t-{sufixo}")
        db.add(tenant)
        db.flush()
        user = User(
            tenant_id=tenant.id,
            email=f"trial-{sufixo}@example.test",
            password_hash="x",
            full_name="Trial",
        )
        db.add(user)
        db.flush()
        agora = datetime.now(timezone.utc)
        db.add(
            Subscription(
                tenant_id=tenant.id,
                user_id=user.id,
                plan_id=plano.id,
                status="trial",
                trial_ends_at=agora + timedelta(days=TRIAL_DURATION_DAYS),
                current_period_start=agora,
                current_period_end=agora + timedelta(days=30),
            )
        )
        db.commit()
        uid, tid = user.id, tenant.id

    yield uid, tid

    with Session() as db:
        db.query(UsageTracking).filter(UsageTracking.user_id == uid).delete(synchronize_session=False)
        db.query(Subscription).filter(Subscription.user_id == uid).delete(synchronize_session=False)
        db.query(User).filter(User.id == uid).delete(synchronize_session=False)
        db.query(Tenant).filter(Tenant.id == tid).delete(synchronize_session=False)
        db.commit()


def _user(db, uid):
    return db.execute(select(User).where(User.id == uid)).scalar_one()


def _usados(uid) -> int:
    with Session() as db:
        linha = db.execute(
            select(UsageTracking).where(
                UsageTracking.user_id == uid, UsageTracking.period == TRIAL_USAGE_PERIOD
            )
        ).scalar_one_or_none()
        return int(cast(int, linha.validations_used)) if linha else 0


# ── Item 9 — fonte única verificável ────────────────────────────────────────


def test_item9_backend_e_frontend_declaram_a_mesma_politica():
    """`trial.ts` do site espelha `trial_policy.json` do backend."""
    ts = (FRONTEND / "src" / "lib" / "trial.ts").read_text(encoding="utf-8")
    politica = trial_policy()
    assert f"TRIAL_DURATION_DAYS = {politica['duration_days']}" in ts
    assert f"TRIAL_VALIDATION_QUOTA = {politica['validation_quota']}" in ts
    assert f'"{politica["quota_period"]}"' in ts


def test_item9_plano_no_banco_bate_com_a_politica():
    """O plano semeado é o que o gate consulta — não pode divergir da decisão."""
    with Session() as db:
        plano = db.execute(select(Plan).where(Plan.slug == "trial")).scalar_one()
        politica = trial_policy()
        assert plano.max_validations == politica["validation_quota"]
        assert plano.trial_days == politica["duration_days"]
        assert bool(plano.has_pdf_reports) is politica["pdf"]
        assert bool(plano.has_api_access) is politica["api"]
        assert bool(plano.has_dashboard) is politica["dashboard"]


# ── Itens 2, 7, 8 — franquia ────────────────────────────────────────────────


def test_item8_janela_do_trial_e_vitalicia_nao_mensal(usuario_trial):
    """Travessia de mês: a chave de período não contém mês-calendário."""
    uid, _ = usuario_trial
    with Session() as db:
        user = _user(db, uid)
        plano = db.execute(select(Plan).where(Plan.slug == "trial")).scalar_one()
        periodo = _periodo_de_uso(db, user, plano)

    assert TRIAL_QUOTA_PERIOD == "trial_lifetime"
    assert periodo == TRIAL_USAGE_PERIOD
    assert not periodo[:4].isdigit(), (
        "período do trial não pode ser YYYY-MM — o reset mensal renovaria a franquia no meio do trial"
    )


def test_item2_sexta_validacao_recusada_antes_do_d3(usuario_trial):
    uid, _ = usuario_trial
    with Session() as db:
        user = _user(db, uid)
        for _ in range(TRIAL_VALIDATION_QUOTA):
            increment_usage(db, user, "validations")
        db.commit()

    assert _usados(uid) == TRIAL_VALIDATION_QUOTA

    with Session() as db:
        user = _user(db, uid)
        with pytest.raises(HTTPException) as exc:
            increment_usage(db, user, "validations")
        assert exc.value.status_code == 403

    assert _usados(uid) == TRIAL_VALIDATION_QUOTA, "franquia não pode ser ultrapassada"


def test_item7_consumo_concorrente_nao_ultrapassa_a_franquia(usuario_trial):
    """Requisições paralelas na 5ª/6ª — o caso que o SELECT-depois-UPDATE perdia."""
    uid, _ = usuario_trial

    with Session() as db:
        user = _user(db, uid)
        for _ in range(TRIAL_VALIDATION_QUOTA - 1):
            increment_usage(db, user, "validations")
        db.commit()
    assert _usados(uid) == TRIAL_VALIDATION_QUOTA - 1

    def tentar(_):
        # Mesmo fluxo do endpoint real (`validate_xml.py`): increment_usage faz
        # flush, e o commit é do chamador.
        with Session() as db:
            try:
                increment_usage(db, _user(db, uid), "validations")
                db.commit()
                return True
            except HTTPException:
                db.rollback()
                return False

    with ThreadPoolExecutor(max_workers=6) as pool:
        aceitos = sum(pool.map(tentar, range(6)))

    assert _usados(uid) == TRIAL_VALIDATION_QUOTA, (
        f"franquia ultrapassada sob concorrência: {_usados(uid)} > {TRIAL_VALIDATION_QUOTA}"
    )
    assert aceitos == 1, "exatamente uma requisição concorrente deve consumir a última unidade"


# ── Item 3 — expiração por data ─────────────────────────────────────────────


def test_item3_apos_d3_recusa_mesmo_com_saldo(usuario_trial):
    uid, _ = usuario_trial
    with Session() as db:
        db.execute(
            update(Subscription)
            .where(Subscription.user_id == uid)
            .values(trial_ends_at=datetime.now(timezone.utc) - timedelta(hours=1))
        )
        db.commit()

    with Session() as db:
        user = _user(db, uid)
        plano = db.execute(select(Plan).where(Plan.slug == "trial")).scalar_one()
        assert _trial_expirado(db, user, plano) is True

        with pytest.raises(HTTPException) as exc:
            check_usage_limit("validations")(current_user=user, db=db)
        assert exc.value.status_code == 403
        assert (exc.value.headers or {}).get("X-Trial-Expired") == "true"

    assert _usados(uid) == 0, "expirou com saldo intacto — a recusa é por data, não por franquia"


# ── Itens 4 e 5 — features contratadas ──────────────────────────────────────


def test_item4_e_5_plano_trial_nao_oferece_pdf_api_dashboard_nem_suporte():
    politica = trial_policy()
    assert politica["txt"] is True
    assert politica["pdf"] is False
    assert politica["api"] is False
    assert politica["dashboard"] is False
    assert politica["technical_support"] is False


def test_item4_endpoint_de_api_key_respeita_has_api_access():
    """O gate que faltava: o endpoint nunca consultou a flag do plano."""
    fonte = (Path(__file__).resolve().parents[1] / "app" / "routers" / "public_api.py").read_text(
        encoding="utf-8"
    )
    assert "has_api_access" in fonte, (
        "criar API key precisa checar has_api_access — sem isso, trial emite chave e ganha créditos"
    )


def test_politica_json_e_o_unico_lugar_com_os_numeros():
    """O JSON é a fonte; o módulo Python só o carrega."""
    bruto = json.loads(
        (Path(__file__).resolve().parents[1] / "app" / "data" / "trial_policy.json").read_text(
            encoding="utf-8"
        )
    )
    assert bruto["duration_days"] == TRIAL_DURATION_DAYS
    assert bruto["validation_quota"] == TRIAL_VALIDATION_QUOTA
