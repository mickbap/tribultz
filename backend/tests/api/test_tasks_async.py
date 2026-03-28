from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.auth import User
from app.services.task_dispatcher import TaskEnqueueResponse, TaskStatusResponse

client = TestClient(app)

mock_user = User(
    id=uuid4(),
    email="tasks@tribultz.com",
    tenant_id=uuid4(),
    full_name="Task Tester",
    is_active=True,
)


def override_get_current_user():
    return mock_user


def override_get_db():
    yield object()


@pytest.fixture(autouse=True)
def dependency_overrides():
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def test_post_validate_dispatches_with_current_tenant():
    response_payload = TaskEnqueueResponse(
        task_id="job-123",
        job_id="job-123",
        status="QUEUED",
    )

    with patch(
        "app.routers.tasks.TaskDispatcher.dispatch",
        return_value=response_payload,
    ) as dispatch_mock:
        response = client.post(
            "/api/v1/tasks/validate",
            json={
                "invoice_number": "INV-001",
                "issue_date": "2026-03-28",
                "declared_cbs": "1.00",
                "declared_ibs": "2.00",
                "items": [{"base_amount": "10.00"}],
            },
        )

    assert response.status_code == 202
    assert response.json() == response_payload.model_dump()
    assert dispatch_mock.call_count == 1
    assert dispatch_mock.call_args.kwargs["tenant_id"] == str(mock_user.tenant_id)


def test_get_task_uses_tenant_scoped_polling():
    response_payload = TaskStatusResponse(
        task_id="job-123",
        job_id="job-123",
        job_type="task_a_validate_cbs_ibs",
        status="RUNNING",
        payload={"invoice_number": "INV-001"},
        result=None,
        error_message=None,
        created_at="2026-03-28T12:00:00+00:00",
        updated_at="2026-03-28T12:00:05+00:00",
    )

    with patch(
        "app.routers.tasks.TaskDispatcher.get_task",
        return_value=response_payload,
    ) as get_task_mock:
        response = client.get("/api/v1/tasks/job-123")

    assert response.status_code == 200
    assert response.json() == response_payload.model_dump()
    assert get_task_mock.call_count == 1
    assert get_task_mock.call_args.kwargs == {
        "task_id": "job-123",
        "tenant_id": str(mock_user.tenant_id),
    }
