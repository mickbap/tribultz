from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class TribultzChatOpsExecutor:
    """
    Runs the ChatOps crew and returns (response_markdown, evidence_list).
    Intent classification is handled by the crew's triage agent.
    """

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    async def handle_message(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        message: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        if self.dry_run:
            job_id = str(uuid4())
            return (
                f"Validation started.\n\nJob: `{job_id}`",
                [
                    {
                        "type": "job",
                        "job_id": job_id,
                        "href": f"/jobs/{job_id}",
                        "label": "Validation job",
                    }
                ],
            )

        from app.crews.chatops_crew import TribultzChatOpsCrew

        crew = TribultzChatOpsCrew(tenant_id=str(tenant_id), user_id=str(user_id))
        try:
            result = await asyncio.to_thread(crew.run, message)
        except Exception as exc:
            logger.error("Crew execution error: %s", exc)
            raise

        response_markdown: str = result.get("response_markdown", "")
        evidence: list[dict[str, Any]] = result.get("evidence", [])
        return response_markdown, evidence
