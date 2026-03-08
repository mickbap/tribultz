from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import SessionLocal


class StatusInput(BaseModel):
    job_id: str = Field(description="UUID of the job to check")


class GetJobStatusTool(BaseTool):
    name: str = "get_job_status"
    description: str = (
        "Get the current status of a job by job_id. "
        "Returns one of: QUEUED, RUNNING, SUCCESS, FAILED, NOT_FOUND."
    )
    args_schema: Type[BaseModel] = StatusInput

    # Injected at construction — enforces tenant scoping
    tenant_id: str

    def _run(self, job_id: str) -> str:
        db = SessionLocal()
        try:
            row = db.execute(
                text(
                    "SELECT status FROM jobs "
                    "WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tid AS uuid)"
                ),
                {"id": job_id, "tid": self.tenant_id},
            ).fetchone()
            return row.status if row else "NOT_FOUND"
        finally:
            db.close()
