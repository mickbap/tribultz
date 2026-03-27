from __future__ import annotations

import json
from typing import Type, cast
from uuid import uuid4

from celery import Task as CeleryTask
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

from app.tasks.task_a_validate import task_a_validate_cbs_ibs
from app.tools.postgres_tool import get_tenant_slug, job_create, job_status_update


class TriggerInput(BaseModel):
    invoice_number: str = Field(
        default="INV-UNKNOWN",
        description="Invoice number extracted from the user message, e.g. INV-001",
    )


class TriggerTaskATool(BaseTool):
    name: str = "trigger_task_a"
    description: str = (
        "Trigger Task A (CBS/IBS validation) for the current tenant. "
        "Provide the invoice_number from the user message. "
        "Returns a JSON string with {job_id}."
    )
    args_schema: Type[BaseModel] = TriggerInput

    # Injected at construction — not exposed to the LLM
    tenant_id: str
    user_id: str
    transaction_id: str | None = None

    def _run(self, invoice_number: str = "INV-UNKNOWN") -> str:
        tenant_slug = get_tenant_slug(self.tenant_id)
        job_id = str(uuid4())

        job_create(
            job_id=job_id,
            tenant_id=self.tenant_id,
            job_type="task_a_validate_cbs_ibs",
            payload={
                "source": "chat",
                "user_id": self.user_id,
                "invoice_number": invoice_number,
                "transaction_id": self.transaction_id,
            },
            idempotency_key=self.transaction_id,
            transaction_id=self.transaction_id,
        )

        t = cast(CeleryTask, task_a_validate_cbs_ibs)
        try:
            t.apply_async(
                kwargs={
                    "tenant_id": self.tenant_id,
                    "tenant_slug": tenant_slug,
                    "invoice_number": invoice_number,
                    "issue_date": "2026-02-16",
                    "declared_cbs": "0",
                    "declared_ibs": "0",
                    "items": [{"sku": "CHAT-ITEM", "base_amount": "100.00"}],
                    "transaction_id": self.transaction_id,
                },
                task_id=job_id,
            )
        except Exception as exc:
            job_status_update(
                job_id=job_id,
                status="FAILED",
                error_message=f"enqueue failed: {exc}",
                transaction_id=self.transaction_id,
            )
            raise

        return json.dumps({"job_id": job_id})
