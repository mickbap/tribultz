"""Tasks API router – HTTP triggers for all Celery tasks."""

from typing import Optional, cast

from celery import Task
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.auth import User
from app.tasks.task_a_validate import task_a_validate_cbs_ibs
from app.tasks.task_b_report import task_b_compliance_report
from app.tasks.task_c_simulation import task_c_whatif_simulation
from app.tasks.task_d_reconciliation import task_d_reconciliation
from app.tasks.task_e_hubspot import task_e_hubspot_sync

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Helpers ───────────────────────────────────────────────────
def _get_tenant_slug(db: Session, tenant_id: str) -> str:
    row = db.execute(
        text("SELECT slug FROM tenants WHERE id = CAST(:id AS uuid)"),
        {"id": tenant_id}
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Tenant {tenant_id} not found")
    return str(row.slug)


# ══════════════════════════════════════════════════════════════
# Task A – Validate CBS/IBS
# ══════════════════════════════════════════════════════════════
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
    async_mode: bool = False


@router.post("/validate")
def trigger_task_a(
    req: TaskARequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = str(current_user.tenant_id)
    tenant_slug = _get_tenant_slug(db, tenant_id)

    items: list[dict[str, object]] = [it.model_dump() for it in req.items]
    if req.async_mode:
        r = cast(Task, task_a_validate_cbs_ibs).delay(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            invoice_number=req.invoice_number,
            issue_date=req.issue_date,
            declared_cbs=req.declared_cbs,
            declared_ibs=req.declared_ibs,
            items=items,
        )
        return {"task_id": r.id, "status": "QUEUED"}
    return task_a_validate_cbs_ibs(  # type: ignore[reportCallIssue]  # Celery bind=True injects self
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        invoice_number=req.invoice_number,
        issue_date=req.issue_date,
        declared_cbs=req.declared_cbs,
        declared_ibs=req.declared_ibs,
        items=items,
    )


# ══════════════════════════════════════════════════════════════
# Task B – Compliance Report
# ══════════════════════════════════════════════════════════════
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
    reference_period: str                  # YYYY-MM
    invoices: list[TaskBInvoice]
    async_mode: bool = False


@router.post("/report")
def trigger_task_b(
    req: TaskBRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = str(current_user.tenant_id)
    tenant_slug = _get_tenant_slug(db, tenant_id)

    invoices: list[dict[str, object]] = [inv.model_dump() for inv in req.invoices]
    if req.async_mode:
        r = cast(Task, task_b_compliance_report).delay(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            company_name=req.company_name,
            cnpj=req.cnpj,
            reference_period=req.reference_period,
            invoices=invoices,
        )
        return {"task_id": r.id, "status": "QUEUED"}
    return task_b_compliance_report(  # type: ignore[reportCallIssue]  # Celery bind=True injects self
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        company_name=req.company_name,
        cnpj=req.cnpj,
        reference_period=req.reference_period,
        invoices=invoices,
    )


# ══════════════════════════════════════════════════════════════
# Task C – What-If Simulation
# ══════════════════════════════════════════════════════════════
class TaskCScenario(BaseModel):
    name: str
    cbs_rate_override: Optional[str] = None
    ibs_rate_override: Optional[str] = None


class TaskCRequest(BaseModel):
    simulation_name: str
    base_amount: str
    scenarios: list[TaskCScenario]
    ref_date: Optional[str] = None
    async_mode: bool = False


@router.post("/simulate")
def trigger_task_c(
    req: TaskCRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = str(current_user.tenant_id)
    tenant_slug = _get_tenant_slug(db, tenant_id)

    scenarios: list[dict[str, object]] = [sc.model_dump() for sc in req.scenarios]
    if req.async_mode:
        r = cast(Task, task_c_whatif_simulation).delay(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            simulation_name=req.simulation_name,
            base_amount=req.base_amount,
            scenarios=scenarios,
            ref_date=req.ref_date,
        )
        return {"task_id": r.id, "status": "QUEUED"}
    return task_c_whatif_simulation(  # type: ignore[reportCallIssue]  # Celery bind=True injects self
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        simulation_name=req.simulation_name,
        base_amount=req.base_amount,
        scenarios=scenarios,
        ref_date=req.ref_date,
    )


# ══════════════════════════════════════════════════════════════
# Task D – Reconciliation
# ══════════════════════════════════════════════════════════════
class TaskDInvoice(BaseModel):
    invoice_number: str
    total_amount: str


class TaskDRequest(BaseModel):
    csv_receivables_b64: str               # base64-encoded CSV
    invoices: list[TaskDInvoice]
    tolerance: str = "0.01"
    async_mode: bool = False


@router.post("/reconcile")
def trigger_task_d(
    req: TaskDRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = str(current_user.tenant_id)
    tenant_slug = _get_tenant_slug(db, tenant_id)

    invoices: list[dict[str, object]] = [inv.model_dump() for inv in req.invoices]
    if req.async_mode:
        r = cast(Task, task_d_reconciliation).delay(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            csv_receivables_b64=req.csv_receivables_b64,
            invoices=invoices,
            tolerance=req.tolerance,
        )
        return {"task_id": r.id, "status": "QUEUED"}
    return task_d_reconciliation(  # type: ignore[reportCallIssue]  # Celery bind=True injects self
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        csv_receivables_b64=req.csv_receivables_b64,
        invoices=invoices,
        tolerance=req.tolerance,
    )


# ══════════════════════════════════════════════════════════════
# Task E – HubSpot Sync
# ══════════════════════════════════════════════════════════════
class TaskERequest(BaseModel):
    company_name: str
    cnpj: str
    domain: Optional[str] = None
    invoices_validated: int = 0
    exceptions_count: int = 0
    deal_value: Optional[str] = None
    async_mode: bool = False


@router.post("/hubspot-sync")
def trigger_task_e(
    req: TaskERequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tenant_id = str(current_user.tenant_id)
    tenant_slug = _get_tenant_slug(db, tenant_id)

    if req.async_mode:
        r = cast(Task, task_e_hubspot_sync).delay(
            tenant_id=tenant_id,
            tenant_slug=tenant_slug,
            company_name=req.company_name,
            cnpj=req.cnpj,
            domain=req.domain,
            invoices_validated=req.invoices_validated,
            exceptions_count=req.exceptions_count,
            deal_value=req.deal_value,
        )
        return {"task_id": r.id, "status": "QUEUED"}
    return task_e_hubspot_sync(  # type: ignore[reportCallIssue]  # Celery bind=True injects self
        tenant_id=tenant_id,
        tenant_slug=tenant_slug,
        company_name=req.company_name,
        cnpj=req.cnpj,
        domain=req.domain,
        invoices_validated=req.invoices_validated,
        exceptions_count=req.exceptions_count,
        deal_value=req.deal_value,
    )
