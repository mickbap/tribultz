from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services.task_dispatcher import TaskDefinition, TaskDispatcher


class FakeResult:
    def __init__(self, row=None):
        self._row = row

    def fetchone(self):
        return self._row


class FakeSession:
    def __init__(self, tenant_slug: str = "tenant-alpha"):
        self.tenant_slug = tenant_slug
        self.jobs: dict[str, SimpleNamespace] = {}
        self.trace: list[tuple[str, str | None]] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        normalized = " ".join(sql.split())

        if normalized.startswith("CREATE TABLE IF NOT EXISTS jobs"):
            self.trace.append(("ensure_jobs", None))
            return FakeResult()

        if "SELECT * FROM jobs WHERE tenant_id = CAST(:tenant_id AS uuid)" in normalized:
            self.trace.append(("find_existing", None))
            for row in self.jobs.values():
                if (
                    str(row.tenant_id) == str(params["tenant_id"])
                    and row.idempotency_key == params["idempotency_key"]
                ):
                    return FakeResult(row)
            return FakeResult()

        if "SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)" in normalized:
            self.trace.append(("tenant_lookup", str(params["id"])))
            return FakeResult(SimpleNamespace(slug=self.tenant_slug))

        if normalized.startswith("INSERT INTO jobs (id, tenant_id, job_type, status, idempotency_key, payload)"):
            task_id = str(params["id"])
            now = datetime.now(timezone.utc)
            self.jobs[task_id] = SimpleNamespace(
                id=task_id,
                tenant_id=str(params["tenant_id"]),
                job_type=str(params["job_type"]),
                status="QUEUED",
                idempotency_key=params["idempotency_key"],
                payload={"invoice_number": "INV-001"},
                result=None,
                error_message=None,
                created_at=now,
                updated_at=now,
            )
            self.trace.append(("insert_job", task_id))
            return FakeResult()

        if normalized.startswith("UPDATE jobs SET status = 'FAILED'"):
            task_id = str(params["id"])
            row = self.jobs[task_id]
            row.status = "FAILED"
            row.error_message = str(params["error_message"])
            row.updated_at = datetime.now(timezone.utc)
            self.trace.append(("mark_failed", task_id))
            return FakeResult()

        if "SELECT * FROM jobs WHERE id = CAST(:id AS uuid)" in normalized:
            task_id = str(params["id"])
            row = self.jobs.get(task_id)
            self.trace.append(("fetch_job", task_id))
            if row and str(row.tenant_id) == str(params["tenant_id"]):
                return FakeResult(row)
            return FakeResult()

        raise AssertionError(f"Unhandled SQL in fake session: {normalized}")

    def commit(self):
        self.trace.append(("commit", None))


class FakeCeleryTask:
    def __init__(self, trace: list[tuple[str, str | None]]):
        self.trace = trace
        self.last_task_id: str | None = None
        self.last_kwargs: dict | None = None

    def apply_async(self, *, kwargs, task_id):
        self.last_task_id = task_id
        self.last_kwargs = kwargs
        self.trace.append(("enqueue", task_id))


def test_dispatch_persists_job_before_enqueue():
    db = FakeSession()
    celery_task = FakeCeleryTask(db.trace)
    dispatcher = TaskDispatcher(db)

    result = dispatcher.dispatch(
        definition=TaskDefinition(job_type="task_a_validate_cbs_ibs", celery_task=celery_task),
        tenant_id="tenant-123",
        payload={"invoice_number": "INV-001"},
        task_kwargs={
            "invoice_number": "INV-001",
            "issue_date": "2026-03-28",
            "declared_cbs": "1.00",
            "declared_ibs": "2.00",
            "items": [{"base_amount": "10.00"}],
        },
    )

    insert_index = db.trace.index(("insert_job", result.task_id))
    enqueue_index = db.trace.index(("enqueue", result.task_id))

    assert insert_index < enqueue_index
    assert result.task_id == result.job_id
    assert result.status == "QUEUED"
    assert celery_task.last_task_id == result.task_id
    assert celery_task.last_kwargs is not None
    assert celery_task.last_kwargs["tenant_id"] == "tenant-123"
    assert celery_task.last_kwargs["tenant_slug"] == "tenant-alpha"


def test_get_task_returns_404_for_missing_tenant_scope():
    db = FakeSession()
    db.jobs["task-1"] = SimpleNamespace(
        id="task-1",
        tenant_id="tenant-a",
        job_type="task_a_validate_cbs_ibs",
        status="QUEUED",
        idempotency_key=None,
        payload={},
        result=None,
        error_message=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    dispatcher = TaskDispatcher(db)

    with pytest.raises(HTTPException) as exc_info:
        dispatcher.get_task(task_id="task-1", tenant_id="tenant-b")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["code"] == "TASK_NOT_FOUND"
