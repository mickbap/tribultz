from __future__ import annotations

from uuid import UUID, uuid4
from typing import cast

from celery import Task

from app.tasks.task_a_validate import task_a_validate_cbs_ibs
from app.tools.postgres_tool import get_tenant_slug, job_create, job_status_update

class TribultzChatOpsExecutor:
    """
    Real executor that calls internal system components.
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    async def trigger_task_a(self, *, tenant_id: UUID, user_id: UUID, message: str) -> UUID:
        """
        Parse message and trigger Task A with a persisted jobs row.
        """
        if self.dry_run:
            return uuid4()

        # MVP parse: look for an INV-* token in the chat text.
        invoice_number = "INV-MVP-CHAT"
        for part in message.split():
            if "INV-" in part.upper():
                invoice_number = part.upper()
                break

        tenant_id_str = str(tenant_id)
        tenant_slug = get_tenant_slug(tenant_id_str)
        job_id = str(uuid4())

        job_create(
            job_id=job_id,
            tenant_id=tenant_id_str,
            job_type="task_a_validate_cbs_ibs",
            payload={
                "source": "chat",
                "user_id": str(user_id),
                "invoice_number": invoice_number,
            },
        )

        t = cast(Task, task_a_validate_cbs_ibs)
        try:
            t.apply_async(
                kwargs={
                    "tenant_id": tenant_id_str,
                    "tenant_slug": tenant_slug,
                    "invoice_number": invoice_number,
                    "issue_date": "2026-02-16",
                    "declared_cbs": "0",
                    "declared_ibs": "0",
                    "items": [{"sku": "CHAT-ITEM", "base_amount": "100.00"}],
                },
                task_id=job_id,
            )
        except Exception as exc:
            job_status_update(job_id=job_id, status="FAILED", error_message=f"enqueue failed: {exc}")
            raise

        return UUID(job_id)

    async def get_job_status(self, *, tenant_id: UUID, user_id: UUID, job_id: UUID) -> str:
        # Check Celery AsyncResult? Or DB?
        # MVP: return "RUNNING"
        return "RUNNING"
