from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from celery import Task
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

_JOBS_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    job_type        VARCHAR(100) NOT NULL,
    status          VARCHAR(30)  NOT NULL DEFAULT 'QUEUED',
    idempotency_key VARCHAR(200),
    payload         JSONB NOT NULL DEFAULT '{}',
    result          JSONB,
    error_message   TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(tenant_id, status);
"""


@dataclass(frozen=True)
class TaskDefinition:
    job_type: str
    celery_task: Task


class TaskEnqueueResponse(BaseModel):
    task_id: str
    job_id: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    job_id: str
    job_type: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error_message: str | None
    created_at: str
    updated_at: str


class TaskDispatcher:
    def __init__(self, db: Session) -> None:
        self._db = db

    def dispatch(
        self,
        *,
        definition: TaskDefinition,
        tenant_id: str,
        payload: dict[str, Any],
        task_kwargs: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> TaskEnqueueResponse:
        self._ensure_jobs_table()

        existing = self._find_existing_job(
            tenant_id=tenant_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return TaskEnqueueResponse(
                task_id=str(existing.id),
                job_id=str(existing.id),
                status=str(existing.status),
            )

        tenant_slug = self._get_tenant_slug(tenant_id)
        job_id = str(uuid4())
        payload_json = json.dumps(payload, default=str)

        self._db.execute(
            text(
                """
                INSERT INTO jobs (id, tenant_id, job_type, status, idempotency_key, payload)
                VALUES (
                    CAST(:id AS uuid),
                    CAST(:tenant_id AS uuid),
                    :job_type,
                    'QUEUED',
                    :idempotency_key,
                    CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "id": job_id,
                "tenant_id": tenant_id,
                "job_type": definition.job_type,
                "idempotency_key": idempotency_key,
                "payload": payload_json,
            },
        )
        self._db.commit()

        try:
            definition.celery_task.apply_async(
                kwargs={
                    **task_kwargs,
                    "tenant_id": tenant_id,
                    "tenant_slug": tenant_slug,
                },
                task_id=job_id,
            )
        except Exception as exc:
            self._mark_enqueue_failure(task_id=job_id, tenant_id=tenant_id, error_message=str(exc))
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "TASK_ENQUEUE_FAILED",
                    "message": "Task queue is unavailable.",
                    "task_id": job_id,
                },
            ) from exc

        return TaskEnqueueResponse(task_id=job_id, job_id=job_id, status="QUEUED")

    def get_task(self, *, task_id: str, tenant_id: str) -> TaskStatusResponse:
        self._ensure_jobs_table()
        row = self._fetch_job(task_id=task_id, tenant_id=tenant_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "TASK_NOT_FOUND",
                    "message": f"Task '{task_id}' was not found for this tenant.",
                },
            )
        return self._row_to_task_status(row)

    def _ensure_jobs_table(self) -> None:
        self._db.execute(text(_JOBS_DDL))
        self._db.commit()

    def _find_existing_job(
        self,
        *,
        tenant_id: str,
        idempotency_key: str | None,
    ):
        if not idempotency_key:
            return None
        return self._db.execute(
            text(
                """
                SELECT *
                FROM jobs
                WHERE tenant_id = CAST(:tenant_id AS uuid)
                  AND idempotency_key = :idempotency_key
                """
            ),
            {
                "tenant_id": tenant_id,
                "idempotency_key": idempotency_key,
            },
        ).fetchone()

    def _get_tenant_slug(self, tenant_id: str) -> str:
        row = self._db.execute(
            text("SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)"),
            {"id": tenant_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Tenant {tenant_id} not found")
        return str(row.slug)

    def _mark_enqueue_failure(
        self,
        *,
        task_id: str,
        tenant_id: str,
        error_message: str,
    ) -> None:
        self._db.execute(
            text(
                """
                UPDATE jobs
                SET status = 'FAILED',
                    error_message = :error_message,
                    updated_at = now()
                WHERE id = CAST(:id AS uuid)
                  AND tenant_id = CAST(:tenant_id AS uuid)
                """
            ),
            {
                "id": task_id,
                "tenant_id": tenant_id,
                "error_message": f"enqueue failed: {error_message}",
            },
        )
        self._db.commit()

    def _fetch_job(self, *, task_id: str, tenant_id: str):
        return self._db.execute(
            text(
                """
                SELECT *
                FROM jobs
                WHERE id = CAST(:id AS uuid)
                  AND tenant_id = CAST(:tenant_id AS uuid)
                """
            ),
            {
                "id": task_id,
                "tenant_id": tenant_id,
            },
        ).fetchone()

    @staticmethod
    def _row_to_task_status(row) -> TaskStatusResponse:
        return TaskStatusResponse(
            task_id=str(row.id),
            job_id=str(row.id),
            job_type=str(row.job_type),
            status=str(row.status),
            payload=row.payload if isinstance(row.payload, dict) else {},
            result=row.result if isinstance(row.result, dict) else None,
            error_message=row.error_message,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )
