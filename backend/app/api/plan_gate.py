"""Plan enforcement dependencies — require_plan, check_usage_limit, increment_usage."""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, cast

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.models.billing import Plan, Subscription, UsageTracking
from app.data.trial_policy import (
    TRIAL_PLAN_SLUG,
    TRIAL_USAGE_PERIOD,
)
from app.models.founding_partner import resolve_effective_license

logger = logging.getLogger(__name__)


def _periodo_de_uso(db: Session, user: User, plan: Any) -> str:
    """Janela de contagem de uso: vitalícia no trial, mensal nos planos pagos (#635).

    `check_usage_limit` usava sempre o mês-calendário. Como o Trial contrata 5
    validações no período INTEIRO (`quota_period = trial_lifetime`), um trial
    ativado no dia 30 ganhava franquia nova no reset do dia 1º — até 10
    validações em 3 dias. A chave fixa `TRIAL` cabe no String(7) da coluna e,
    somada à unique (user_id, period), dá exatamente UMA linha por usuário
    durante todo o trial. Sem migration.

    Ao migrar para um plano pago o período volta a ser mensal: a franquia nova é
    a do plano contratado, e a linha TRIAL fica como histórico.
    """
    if plan is not None and cast(str, plan.slug) == TRIAL_PLAN_SLUG:
        return TRIAL_USAGE_PERIOD
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _trial_expirado(db: Session, user: User, plan: Any) -> bool:
    """Trial vencido por data, checado de forma síncrona (#635, item 3 da régua).

    A expiração existia só na task Celery `expire_trials` (task_g_billing), que
    roda pelo beat. Entre o D+3 e a próxima execução da task o usuário seguia
    validando com saldo. Aqui a checagem acontece na porta, então o vencimento
    não depende de agendador.
    """
    if plan is None or cast(str, plan.slug) != TRIAL_PLAN_SLUG:
        return False
    sub, _ = _get_active_subscription(db, user)
    if sub is None or sub.trial_ends_at is None:
        return False
    fim = sub.trial_ends_at
    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=timezone.utc)
    return fim < datetime.now(timezone.utc)


def require_plan(*allowed_slugs: str) -> Callable:
    """FastAPI Depends factory — raises 403 if user's plan is not in allowed_slugs."""

    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        plan = _get_effective_plan(db, current_user)
        slug = cast(str, plan.slug) if plan else None

        if slug not in allowed_slugs:
            plan_names = ", ".join(s.capitalize() for s in allowed_slugs)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Recurso disponível nos planos: {plan_names}. Faça upgrade para continuar.",
                headers={"X-Upgrade-Required": "true"},
            )
        return current_user

    return _check


def check_usage_limit(usage_type: str) -> Callable:
    """FastAPI Depends factory — raises 403 if monthly usage limit is reached.

    usage_type: 'validations' or 'ai_messages'
    """

    def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        plan = _get_effective_plan(db, current_user)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Nenhum plano ativo. Faça upgrade para continuar.",
            )

        # Get the limit from plan
        if usage_type == "validations":
            limit = plan.max_validations  # NULL = unlimited
        elif usage_type == "ai_messages":
            limit = plan.max_ai_messages
        else:
            return current_user  # unknown type, skip check

        # Trial vencido por data barra antes da franquia: item 3 da régua —
        # "após D+3, validação recusada mesmo com saldo".
        if _trial_expirado(db, current_user, plan):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Período de teste encerrado. Assine um plano para continuar validando.",
                headers={"X-Trial-Expired": "true"},
            )

        # NULL means unlimited
        if limit is None:
            return current_user

        # Check current usage
        period = _periodo_de_uso(db, current_user, plan)
        usage = db.execute(
            select(UsageTracking).where(
                UsageTracking.user_id == current_user.id,
                UsageTracking.period == period,
            )
        ).scalar_one_or_none()

        current = 0
        if usage:
            if usage_type == "validations":
                current = cast(int, usage.validations_used)
            else:
                current = cast(int, usage.ai_messages_used)

        if current >= cast(int, limit):
            janela = "do período de teste" if period == TRIAL_USAGE_PERIOD else "mensal"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Limite {janela} de {usage_type.replace('_', ' ')} atingido "
                    f"({current}/{limit}). Faça upgrade para continuar."
                ),
                headers={"X-Usage-Limit-Reached": "true"},
            )

        return current_user

    return _check


def increment_usage(
    db: Session,
    user: User,
    usage_type: str,
    *,
    enforce_limit: bool = True,
) -> None:
    """Consome uma unidade da franquia, de forma atômica.

    Chamar DEPOIS de uma validação/mensagem bem-sucedida.

    Atomicidade (#635, item 7 da régua): antes eram duas instruções — SELECT da
    linha e UPDATE incrementando —, e a checagem de limite vivia noutro lugar
    (`check_usage_limit`, como dependency). Duas requisições paralelas na 5ª
    validação passavam ambas pela checagem com `current=4` e incrementavam as
    duas: 6 usos numa franquia de 5.

    Agora o consumo é um único `INSERT … ON CONFLICT DO UPDATE … WHERE usado <
    limite`. Quem perde a corrida não atualiza linha nenhuma e recebe 403 — a
    franquia nunca é ultrapassada, independentemente de quantas requisições
    chegarem juntas.

    A janela é a mesma de `check_usage_limit` (vitalícia no trial, mensal nos
    planos pagos): as duas pontas precisam concordar, senão a contagem se perde.
    """
    plan = _get_effective_plan(db, user)
    period = _periodo_de_uso(db, user, plan)

    coluna = {
        "validations": UsageTracking.validations_used,
        "ai_messages": UsageTracking.ai_messages_used,
    }.get(usage_type)
    if coluna is None:
        return

    limite = None
    if plan is not None:
        limite = plan.max_validations if usage_type == "validations" else plan.max_ai_messages

    valores = {
        "tenant_id": user.tenant_id,
        "user_id": user.id,
        "period": period,
        coluna.key: 1,
    }
    stmt = pg_insert(UsageTracking).values(**valores)

    # No ramo de conflito, `coluna` referencia o valor JÁ gravado na linha.
    set_ = {coluna.key: coluna + 1}

    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "period"],
        set_=set_,
        where=(coluna < limite) if (enforce_limit and limite is not None) else None,
    ).returning(coluna)

    consumido = db.execute(stmt).scalar_one_or_none()
    db.flush()

    if consumido is None and enforce_limit and limite is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Limite de {usage_type.replace('_', ' ')} atingido ({limite}/{limite}). "
                "Faça upgrade para continuar."
            ),
            headers={"X-Usage-Limit-Reached": "true"},
        )


def get_plan_slug(db: Session, user: User) -> str | None:
    """Return the effective plan slug for a user (Grant Adapter aware), or None."""
    plan = _get_effective_plan(db, user)
    if plan is None:
        return None
    return str(plan.slug)


def get_effective_plan(db: Session, user: User) -> Any:
    """Public wrapper — resolve o Plan completo (não só o slug) do usuário."""
    return _get_effective_plan(db, user)


def _get_effective_plan(db: Session, user: User) -> Any:
    """Resolve o Plan efetivo do usuário — Grant ativo (ADR-0008, Grant Adapter)
    tem precedência sobre a assinatura, mesmo ponto único de resolução já usado
    no login (`auth.py`: ``resolve_effective_license``). Sem isso, um Early
    Adopter com Grant ativo (sem Subscription — RNF002) nunca passava em
    `require_plan`/`check_usage_limit`/`get_plan_slug`, apesar do JWT reportar
    o plano correto (#487).

    Ator ``partner`` (RFC-0026) não tem ``tenant_id`` — não há Grant possível,
    devolve a assinatura como está (tipicamente None).
    """
    _sub, sub_plan = _get_active_subscription(db, user)
    if user.tenant_id is None:
        return sub_plan
    base_slug = cast(str, sub_plan.slug) if sub_plan is not None else ""
    effective_slug, source = resolve_effective_license(db, cast(Any, user.tenant_id), base_slug)
    if source == "subscription":
        return sub_plan
    return db.execute(select(Plan).where(Plan.slug == effective_slug)).scalar_one_or_none()


def _get_active_subscription(db: Session, user: User) -> tuple[Any, Any]:
    """Get the user's most recent subscription + plan. Returns (sub, plan) or (None, None)."""
    result = db.execute(
        select(Subscription, Plan)
        .join(Plan, Subscription.plan_id == Plan.id)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_(("active", "trial", "pending", "cancelled")),
        )
        .order_by(Subscription.created_at.desc())
        .limit(1)
    ).first()

    if not result:
        return (None, None)

    sub, plan = result[0], result[1]

    # Cancelled subs: only grant access if period hasn't ended
    if cast(str, sub.status) == "cancelled":
        if sub.current_period_end is not None:
            period_end = cast(datetime, sub.current_period_end)
            if period_end < datetime.now(timezone.utc):
                return (None, None)
        else:
            return (None, None)

    return (sub, plan)
