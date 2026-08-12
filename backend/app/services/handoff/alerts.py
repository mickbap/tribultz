"""Alerta operacional e escalonamento do Caminho C (Round 7 §7).

O sistema detecta, protege localmente, alerta, exige evidência, escala e
registra — quem PARA o bot é uma pessoa, na tela do Rumy. Nada aqui religa
outbound; falha de alerta nunca quebra o ingest (best-effort com trilha).

Escada: T+0 alerta primário → SLA de pausa (5 min úteis) estourado ⇒
escalonamento → 2× SLA sem confirmação ⇒ EXPOSIÇÃO NÃO CONTIDA (incidente,
falhar alto é a única alavanca que resta). Timeout jamais devolve o lead à
automação.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.crm_handoff import CrmLeadLink, CrmStateTransition
from app.services.handoff.ownership import (
    ActorType,
    business_hours_between,
    pause_pending,
    pause_sla,
    pause_sla_breached,
    uncontained_exposure,
)

logger = logging.getLogger(__name__)

_ALERT_AXIS = "alert"
ALERT_RAISED = "pause_alert_raised"
ALERT_ESCALATED = "pause_sla_escalated"
ALERT_UNCONTAINED = "uncontained_exposure"


def _now(now: Optional[datetime]) -> datetime:
    return now or datetime.now(timezone.utc)


def _has_alert(session: Session, link: CrmLeadLink, to_state: str) -> bool:
    return session.query(
        session.query(CrmStateTransition)
        .filter(
            CrmStateTransition.lead_link_id == link.id,
            CrmStateTransition.axis == _ALERT_AXIS,
            CrmStateTransition.to_state == to_state,
            CrmStateTransition.created_at >= link.handoff_requested_at,
        )
        .exists()
    ).scalar()


def _audit_alert(session: Session, link: CrmLeadLink, to_state: str, reason: str) -> None:
    session.add(
        CrmStateTransition(
            tenant_id=link.tenant_id,
            lead_link_id=link.id,
            axis=_ALERT_AXIS,
            from_state=None,
            to_state=to_state,
            actor_type=ActorType.SYSTEM.value,
            actor_ref="handoff-alerts",
            reason=reason,
        )
    )


def _oncall_emails() -> list[str]:
    return [e.strip() for e in settings.HANDOFF_ALERT_EMAILS.split(",") if e.strip()]


class CaminhoCNotActivatable(Exception):
    """Round 8 §7: sem plantão configurado, o Caminho C não é ativável."""


def caminho_c_ready() -> tuple[bool, list[str]]:
    """Gate de ativação do Caminho C — fail-closed explícito (Round 8 §7).

    A PROTEÇÃO local (DEC-1/DEC-5) nunca depende disto — ela se aplica sempre.
    O que este gate bloqueia é a OPERAÇÃO assistida (alerta/escalonamento/
    piloto): alerta sem destinatário é decoração de sistema.
    """
    missing = []
    if not _oncall_emails():
        missing.append("HANDOFF_ALERT_EMAILS vazio — plantão não configurado (Produto define)")
    return (not missing, missing)


def assert_caminho_c_activatable() -> None:
    ok, missing = caminho_c_ready()
    if not ok:
        raise CaminhoCNotActivatable("; ".join(missing))


def raise_pause_alert(
    session: Session,
    link: CrmLeadLink,
    person_display: str = "",
    campaign: str = "",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Alerta primário (T+0): task "PAUSAR AUTOMAÇÃO NO RUMY" + e-mail ao plantão.

    Idempotente por ciclo de handoff (dedupe pela trilha de auditoria) — retry
    de evento não duplica alerta. Best-effort: falha em e-mail/task vira log e
    campo no resultado, nunca exceção para o chamador.
    """
    ts = _now(now)
    if _has_alert(session, link, ALERT_RAISED):
        return {"raised": False, "detail": "alert_already_raised"}

    deadline = ts + pause_sla()
    summary = (
        f"PAUSAR AUTOMAÇÃO NO RUMY — lead {link.external_lead_id}"
        f"{f' · {person_display}' if person_display else ''}"
        f"{f' · campanha {campaign}' if campaign else ''}"
        f" · handoff {link.handoff_requested_at.isoformat() if link.handoff_requested_at else '?'}"
        f" · SLA de pausa: {settings.HANDOFF_PAUSE_SLA_MINUTES} min úteis"
        f" · prioridade CRÍTICA"
    )
    _audit_alert(session, link, ALERT_RAISED, summary)

    email_sent = False
    recipients = _oncall_emails()
    if not recipients:
        # §7: sem plantão o alerta é INENTREGÁVEL — registrado como crítico,
        # jamais como caminho normal. A trava local já foi aplicada antes.
        _audit_alert(
            session, link, "pause_alert_undeliverable",
            "plantão não configurado (HANDOFF_ALERT_EMAILS vazio) — alerta sem "
            "destinatário é decoração; Caminho C não ativável (Round 8 §7)",
        )
        logger.error("handoff_alert_undeliverable link=%s — plantão não configurado", link.id)
    if recipients:
        try:
            from app.services.email_service import send_handoff_pause_alert_email

            for to in recipients:
                email_sent = send_handoff_pause_alert_email(
                    to_email=to,
                    lead_ref=link.external_lead_id,
                    person_display=person_display or "(pessoa não identificada)",
                    campaign=campaign or "(sem campanha)",
                    requested_at_iso=(
                        link.handoff_requested_at.isoformat()
                        if link.handoff_requested_at
                        else ts.isoformat()
                    ),
                    pause_sla_minutes=settings.HANDOFF_PAUSE_SLA_MINUTES,
                ) or email_sent
        except Exception:  # noqa: BLE001 — alerta nunca derruba o ingest
            logger.exception("handoff_alert_email_failed link=%s", link.id)

    task_created = False
    try:
        from app.integrations.attio.tasks import create_pause_task

        linked = []
        if link.attio_person_id:
            linked.append({"target_object": "people", "target_record_id": link.attio_person_id})
        result = create_pause_task(summary, deadline.isoformat(), linked_records=linked)
        task_created = bool(result) and result.get("noop") is None
    except Exception:  # noqa: BLE001
        logger.exception("handoff_alert_attio_task_failed link=%s", link.id)

    session.flush()
    logger.info(
        "handoff_pause_alert link=%s email=%s attio_task=%s deadline=%s",
        link.id, email_sent, task_created, deadline.isoformat(),
    )
    return {
        "raised": True,
        "email_sent": email_sent,
        "attio_task_created": task_created,
        "deadline": deadline.isoformat(),
    }


def escalate_overdue(session: Session, now: Optional[datetime] = None) -> dict[str, int]:
    """Varredura de escalonamento (§7): idempotente por nível e por ciclo.

    Nível 1: SLA de pausa estourado ⇒ re-alerta. Nível 2: 2× SLA ⇒ marca
    EXPOSIÇÃO NÃO CONTIDA (entra na contagem de incidentes). Nunca devolve
    lead à automação — a alavanca final é falhar alto.
    """
    assert_caminho_c_activatable()  # §7: sem plantão, escalonar é teatro
    ts = _now(now)
    escalated = uncontained = 0
    pending = (
        session.query(CrmLeadLink)
        .filter(CrmLeadLink.automation_state == "SUPPRESSION_REQUESTED")
        .all()
    )
    for link in pending:
        if not pause_pending(link):
            continue
        if uncontained_exposure(link, now=ts) and not _has_alert(session, link, ALERT_UNCONTAINED):
            elapsed = business_hours_between(link.handoff_requested_at, ts)
            _audit_alert(
                session, link, ALERT_UNCONTAINED,
                f"exposição não contida: {elapsed} úteis sem confirmação de pausa "
                f"(2× SLA) — incidente",
            )
            uncontained += 1
        elif pause_sla_breached(link, now=ts) and not _has_alert(session, link, ALERT_ESCALATED):
            _audit_alert(
                session, link, ALERT_ESCALATED,
                f"SLA de pausa ({settings.HANDOFF_PAUSE_SLA_MINUTES} min úteis) estourado — "
                f"escalonando ao nível seguinte",
            )
            escalated += 1
    session.flush()
    if escalated or uncontained:
        logger.warning(
            "handoff_escalation escalated=%s uncontained=%s", escalated, uncontained
        )
    return {"escalated": escalated, "uncontained": uncontained, "pending": len(pending)}
