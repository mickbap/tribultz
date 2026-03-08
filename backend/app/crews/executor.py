from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID, uuid4

from app.config import settings

logger = logging.getLogger(__name__)

CREW_ERROR_MESSAGE = "Crew execution failed"


class CrewExecutionError(RuntimeError):
    """Raised when the Crew runtime fails for non-timeout reasons."""


class CrewExecutionTimeoutError(CrewExecutionError):
    """Raised when the Crew runtime exceeds the allowed timeout."""


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
        timeout_s = max(1, int(settings.CHATOPS_TIMEOUT_SECONDS))
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.run, message),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "Crew execution timeout (tenant_id=%s user_id=%s timeout_s=%s)",
                tenant_id,
                user_id,
                timeout_s,
            )
            raise CrewExecutionTimeoutError(CREW_ERROR_MESSAGE) from exc
        except Exception as exc:
            logger.exception(
                "Crew execution error (tenant_id=%s user_id=%s): %s",
                tenant_id,
                user_id,
                exc,
            )
            raise CrewExecutionError(CREW_ERROR_MESSAGE) from exc

        response_markdown: str = result.get("response_markdown", "")
        evidence: list[dict[str, Any]] = result.get("evidence", [])
        return response_markdown, evidence
