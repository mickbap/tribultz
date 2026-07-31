"""History logging — Attio CRM.

PO-2026-07-CRM-001, fatia 6/12. Each call creates a new note (POST /v2/notes,
docs.attio.com/rest-api/endpoint-reference/notes/create-a-note) — this is an
append-only history log, not an upsert. Unlike companies.py/people.py there
is deliberately no dedup here: history is a log of events, so a repeated
call legitimately creates a second note. The client's retry policy already
refuses to retry POST on 5xx (see client.py) precisely to avoid an
ambiguous retry silently duplicating a note.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)

# PO seção 8 — os seis tipos de evento de histórico rastreados.
_EVENT_TITLES: dict[str, str] = {
    "criacao": "Lead criado",
    "atualizacao": "Lead atualizado",
    "mudanca_estagio": "Estágio alterado",
    "campanha_enviada": "Campanha enviada",
    "resposta_recebida": "Resposta recebida",
    "observacao": "Observação automática",
}


def log_history(
    parent_record_id: str,
    event_type: str,
    content: str,
    parent_object: str = "companies",
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Append a history note to a record's timeline.

    event_type must be one of the PO's six tracked event kinds; anything
    else raises ValueError before touching the API.
    """
    if event_type not in _EVENT_TITLES:
        raise ValueError(
            f"tipo de evento de histórico inválido: {event_type!r} — "
            f"esperado um de {tuple(_EVENT_TITLES)}"
        )

    if not is_enabled():
        return noop("history_note")

    client = client or AttioClient()
    logger.info("attio_history_log object=%s event_type=%s", parent_object, event_type)
    return client.request(
        "POST",
        "/notes",
        json={
            "data": {
                "parent_object": parent_object,
                "parent_record_id": parent_record_id,
                "title": _EVENT_TITLES[event_type],
                "format": "plaintext",
                "content": content,
            }
        },
    )
