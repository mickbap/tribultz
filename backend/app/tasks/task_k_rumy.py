"""Worker assíncrono do inbox Rumy (F2, Round 5 da PO-2026-07-CRM-001).

Wrapper fino sobre inbox.process_raw_event — a lógica vive no serviço (testável
sem broker). Retry exponencial só para ProcessingError (falha transitória);
quarentena/unmapped/duplicado não re-tentam (retry não conserta payload).

Com HANDOFF_APPLY_ENABLED=false (default) o processamento é shadow mode: o
evento fica no ledger e nada é aplicado ao domínio.
"""

from __future__ import annotations

import logging
import uuid

from app.celery_app import celery
from app.database import SessionLocal
from app.services.handoff.inbox import ProcessingError, process_raw_event

logger = logging.getLogger(__name__)


@celery.task(
    name="handoff.process_rumy_event",
    bind=True,
    max_retries=5,
    default_retry_delay=30,
)
def process_rumy_event(self, ledger_id: str):
    """Processa uma linha bruta do inbox (adapter → contrato → domínio)."""
    session = SessionLocal()
    try:
        result = process_raw_event(session, uuid.UUID(ledger_id))
        session.commit()
        return result
    except ProcessingError as exc:
        session.commit()  # persiste o status 'failed' + error antes do retry
        logger.warning("handoff_worker_retry ledger=%s err=%s", ledger_id, exc)
        raise self.retry(exc=exc, countdown=min(30 * (2**self.request.retries), 600))
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@celery.task(name="handoff.escalate_overdue")
def escalate_overdue_task():
    """Varredura de escalonamento do Caminho C (Round 7 §7).

    Registrada mas DELIBERADAMENTE fora do beat schedule — a ativação do
    agendamento é decisão do round de piloto. Rodar manualmente ou via beat
    quando autorizado.
    """
    from app.services.handoff.alerts import escalate_overdue

    session = SessionLocal()
    try:
        result = escalate_overdue(session)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
