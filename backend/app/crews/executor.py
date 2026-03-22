from __future__ import annotations

import asyncio
import logging
import time
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
        t0 = time.monotonic()

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.run, message),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            elapsed = time.monotonic() - t0
            logger.error(
                "crew_timeout tenant=%s user=%s timeout_s=%s elapsed=%.2fs",
                tenant_id,
                user_id,
                timeout_s,
                elapsed,
            )
            raise CrewExecutionTimeoutError(CREW_ERROR_MESSAGE) from exc
        except Exception as exc:
            elapsed = time.monotonic() - t0
            logger.exception(
                "crew_error tenant=%s user=%s elapsed=%.2fs error=%s",
                tenant_id,
                user_id,
                elapsed,
                str(exc)[:200],
            )
            raise CrewExecutionError(CREW_ERROR_MESSAGE) from exc

        elapsed = time.monotonic() - t0
        logger.info(
            "crew_complete tenant=%s user=%s elapsed=%.2fs",
            tenant_id,
            user_id,
            elapsed,
        )

        response_markdown: str = result.get("response_markdown", "")
        evidence: list[dict[str, Any]] = result.get("evidence", [])
        return response_markdown, evidence
