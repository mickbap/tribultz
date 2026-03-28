"""Tasks API router: async-only task dispatch and polling."""

from __future__ import annotations

from typing import Any, cast

from celery import Task
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.services.task_dispatcher import (
    TaskDefinition,
    TaskDispatcher,
    TaskEnqueueResponse,
    TaskStatusResponse,
)
from app.tasks.task_a_validate import task_a_validate_cbs_ibs
from app.tasks.task_b_report import task_b_compliance_report
from app.tasks.task_c_simulation import task_c_whatif_simulation
from app.tasks.task_d_reconciliation import task_d_reconciliation
from app.tasks.task_e_hubspot import task_e_hubspot_sync

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])

TASK_A = TaskDefinition(
    job_type="task_a_validate_cbs_ibs",
    celery_task=cast(Task, task_a_validate_cbs_ibs),
)
TASK_B = TaskDefinition(
    job_type="task_b_compliance_report",
    celery_task=cast(Task, task_b_compliance_report),
)
TASK_C = TaskDefinition(
    job_type="task_c_whatif_simulation",
    celery_task=cast(Task, task_c_whatif_simulation),
)
TASK_D = TaskDefinition(
    job_type="task_d_reconciliation",
    celery_task=cast(Task, task_d_reconciliation),
)
TASK_E = TaskDefinition(
    job_type="task_e_hubspot_sync",
    celery_task=cast(Task, task_e_hubspot_sync),
)


class TaskAItem(BaseModel):
    sku: str = ""
    description: str = ""
    base_amount: str
    cbs_rule_code: str = "STD_CBS"
    ibs_rule_code: str = "STD_IBS"


class TaskARequest(BaseModel):
    invoice_number: str
    issue_date: str
    declared_cbs: str
    declared_ibs: str
    items: list[TaskAItem]
    async_mode: bool = True


class TaskBInvoiceItem(BaseModel):
    base_amount: str


class TaskBInvoice(BaseModel):
    invoice_number: str
    declared_cbs: str = "0"
    declared_ibs: str = "0"
    items: list[TaskBInvoiceItem]


class TaskBRequest(BaseModel):
    company_name: str
    cnpj: str
    reference_period: str
    invoices: list[TaskBInvoice]
    async_mode: bool = True


class TaskCScenario(BaseModel):
    name: str
    cbs_rate_override: str | None = None
    ibs_rate_override: str | None = None


class TaskCRequest(BaseModel):
    simulation_name: str
    base_amount: str
    scenarios: list[TaskCScenario]
    ref_date: str | None = None
    async_mode: bool = True


class TaskDInvoice(BaseModel):
    invoice_number: str
    total_amount: str


class TaskDRequest(BaseModel):
    csv_receivables_b64: str
    invoices: list[TaskDInvoice]
    tolerance: str = "0.01"
    async_mode: bool = True


class TaskERequest(BaseModel):
    company_name: str
    cnpj: str
    domain: str | None = None
    invoices_validated: int = 0
    exceptions_count: int = 0
    deal_value: str | None = None
    async_mode: bool = True


def _dispatcher(db: Session) -> TaskDispatcher:
    return TaskDispatcher(db)


def _dispatch_task(
    *,
    definition: TaskDefinition,
    tenant_id: str,
    payload: dict[str, Any],
    task_kwargs: dict[str, Any],
    db: Session,
) -> TaskEnqueueResponse:
    return _dispatcher(db).dispatch(
        definition=definition,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs=task_kwargs,
    )


@router.post("/validate", response_model=TaskEnqueueResponse, status_code=202)
def trigger_task_a(
    req: TaskARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskEnqueueResponse:
    tenant_id = str(current_user.tenant_id)
    items = [item.model_dump() for item in req.items]
    payload = req.model_dump(exclude={"async_mode"})
    return _dispatch_task(
        definition=TASK_A,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs={
            "invoice_number": req.invoice_number,
            "issue_date": req.issue_date,
            "declared_cbs": req.declared_cbs,
            "declared_ibs": req.declared_ibs,
            "items": items,
        },
        db=db,
    )


@router.post("/report", response_model=TaskEnqueueResponse, status_code=202)
def trigger_task_b(
    req: TaskBRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskEnqueueResponse:
    tenant_id = str(current_user.tenant_id)
    invoices = [invoice.model_dump() for invoice in req.invoices]
    payload = req.model_dump(exclude={"async_mode"})
    return _dispatch_task(
        definition=TASK_B,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs={
            "company_name": req.company_name,
            "cnpj": req.cnpj,
            "reference_period": req.reference_period,
            "invoices": invoices,
        },
        db=db,
    )


@router.post("/simulate", response_model=TaskEnqueueResponse, status_code=202)
def trigger_task_c(
    req: TaskCRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskEnqueueResponse:
    tenant_id = str(current_user.tenant_id)
    scenarios = [scenario.model_dump() for scenario in req.scenarios]
    payload = req.model_dump(exclude={"async_mode"})
    return _dispatch_task(
        definition=TASK_C,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs={
            "simulation_name": req.simulation_name,
            "base_amount": req.base_amount,
            "scenarios": scenarios,
            "ref_date": req.ref_date,
        },
        db=db,
    )


@router.post("/reconcile", response_model=TaskEnqueueResponse, status_code=202)
def trigger_task_d(
    req: TaskDRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskEnqueueResponse:
    tenant_id = str(current_user.tenant_id)
    invoices = [invoice.model_dump() for invoice in req.invoices]
    payload = req.model_dump(exclude={"async_mode"})
    return _dispatch_task(
        definition=TASK_D,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs={
            "csv_receivables_b64": req.csv_receivables_b64,
            "invoices": invoices,
            "tolerance": req.tolerance,
        },
        db=db,
    )


@router.post("/hubspot-sync", response_model=TaskEnqueueResponse, status_code=202)
def trigger_task_e(
    req: TaskERequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskEnqueueResponse:
    tenant_id = str(current_user.tenant_id)
    payload = req.model_dump(exclude={"async_mode"})
    return _dispatch_task(
        definition=TASK_E,
        tenant_id=tenant_id,
        payload=payload,
        task_kwargs={
            "company_name": req.company_name,
            "cnpj": req.cnpj,
            "domain": req.domain,
            "invoices_validated": req.invoices_validated,
            "exceptions_count": req.exceptions_count,
            "deal_value": req.deal_value,
        },
        db=db,
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskStatusResponse:
    return _dispatcher(db).get_task(
        task_id=task_id,
        tenant_id=str(current_user.tenant_id),
    )
