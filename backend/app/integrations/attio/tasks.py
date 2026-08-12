"""Task operacional no Attio — alerta de pausa do Caminho C (Round 7 §7).

Cria a task "PAUSAR AUTOMAÇÃO NO RUMY" ligada aos records do lead, com
deadline = SLA de pausa. Mesmo padrão dos demais módulos: sem ATTIO_ENABLED
ou sem API key, é no-op — nenhuma superfície externa por padrão.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)


def create_pause_task(
    content: str,
    deadline_at_iso: str,
    linked_records: Optional[list[dict[str, str]]] = None,
    assignee_member_ids: Optional[list[str]] = None,
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """POST /v2/tasks — task plaintext com deadline e records vinculados."""
    if not is_enabled():
        return noop("task")
    client = client or AttioClient()
    logger.info("attio_task_create deadline=%s", deadline_at_iso)
    return client.request(
        "POST",
        "/tasks",
        json={
            "data": {
                "content": content,
                "format": "plaintext",
                "deadline_at": deadline_at_iso,
                "is_completed": False,
                "linked_records": linked_records or [],
                "assignees": [
                    {"referenced_actor_type": "workspace-member", "referenced_actor_id": m}
                    for m in (assignee_member_ids or [])
                ],
            }
        },
    )
