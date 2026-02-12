"""Tasks API router – HTTP triggers for all Celery tasks."""

import base64
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.tasks.task_a_validate import task_a_validate_cbs_ibs
from app.tasks.task_b_report import task_b_compliance_report
from app.tasks.task_c_simulation import task_c_whatif_simulation
from app.tasks.task_d_reconciliation import task_d_reconciliation
from app.tasks.task_e_hubspot import task_e_hubspot_sync

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# ── Helpers ───────────────────────────────────────────────────
def _tenant_id(db: Session, slug: str) -> str:
    row = db.execute(
        text("SELECT id FROM tenants WHERE slug = :slug"), {"slug": slug}
    ).fetchone()
    if not row:
        raise HTTPException(404, f"Tenant '{slug}' not found")
    return str(row.id)


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
    tenant_slug: str = "default"
    invoice_number: str
    issue_date: str
    declared_cbs: str
    declared_ibs: str
    items: list[TaskAItem]
    async_mode: bool = False


@router.post("/validate")
def trigger_task_a(req: TaskARequest, db: Session = Depends(get_db)):
    tid = _tenant_id(db, req.tenant_slug)
    items = [it.model_dump() for it in req.items]
    kwargs = dict(
        tenant_id=tid,
        tenant_slug=req.tenant_slug,
        invoice_number=req.invoice_number,
        issue_date=req.issue_date,
        declared_cbs=req.declared_cbs,
        declared_ibs=req.declared_ibs,
        items=items,
    )
    if req.async_mode:
        r = task_a_validate_cbs_ibs.delay(**kwargs)
        return {"task_id": r.id, "status": "QUEUED"}
    return task_a_validate_cbs_ibs(**kwargs)


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
    tenant_slug: str = "default"
    company_name: str
    cnpj: str
    reference_period: str                  # YYYY-MM
    invoices: list[TaskBInvoice]
    async_mode: bool = False


@router.post("/report")
def trigger_task_b(req: TaskBRequest, db: Session = Depends(get_db)):
    tid = _tenant_id(db, req.tenant_slug)
    kwargs = dict(
        tenant_id=tid,
        tenant_slug=req.tenant_slug,
        company_name=req.company_name,
        cnpj=req.cnpj,
        reference_period=req.reference_period,
        invoices=[inv.model_dump() for inv in req.invoices],
    )
    if req.async_mode:
        r = task_b_compliance_report.delay(**kwargs)
        return {"task_id": r.id, "status": "QUEUED"}
    return task_b_compliance_report(**kwargs)


# ══════════════════════════════════════════════════════════════
# Task C – What-If Simulation
# ══════════════════════════════════════════════════════════════
class TaskCScenario(BaseModel):
    name: str
    cbs_rate_override: Optional[str] = None
    ibs_rate_override: Optional[str] = None


class TaskCRequest(BaseModel):
    tenant_slug: str = "default"
    simulation_name: str
    base_amount: str
    scenarios: list[TaskCScenario]
    ref_date: Optional[str] = None
    async_mode: bool = False


@router.post("/simulate")
def trigger_task_c(req: TaskCRequest, db: Session = Depends(get_db)):
    tid = _tenant_id(db, req.tenant_slug)
    kwargs = dict(
        tenant_id=tid,
        tenant_slug=req.tenant_slug,
        simulation_name=req.simulation_name,
        base_amount=req.base_amount,
        scenarios=[sc.model_dump() for sc in req.scenarios],
        ref_date=req.ref_date,
    )
    if req.async_mode:
        r = task_c_whatif_simulation.delay(**kwargs)
        return {"task_id": r.id, "status": "QUEUED"}
    return task_c_whatif_simulation(**kwargs)


# ══════════════════════════════════════════════════════════════
# Task D – Reconciliation
# ══════════════════════════════════════════════════════════════
class TaskDInvoice(BaseModel):
    invoice_number: str
    total_amount: str


class TaskDRequest(BaseModel):
    tenant_slug: str = "default"
    csv_receivables_b64: str               # base64-encoded CSV
    invoices: list[TaskDInvoice]
    tolerance: str = "0.01"
    async_mode: bool = False


@router.post("/reconcile")
def trigger_task_d(req: TaskDRequest, db: Session = Depends(get_db)):
    tid = _tenant_id(db, req.tenant_slug)
    kwargs = dict(
        tenant_id=tid,
        tenant_slug=req.tenant_slug,
        csv_receivables_b64=req.csv_receivables_b64,
        invoices=[inv.model_dump() for inv in req.invoices],
        tolerance=req.tolerance,
    )
    if req.async_mode:
        r = task_d_reconciliation.delay(**kwargs)
        return {"task_id": r.id, "status": "QUEUED"}
    return task_d_reconciliation(**kwargs)


# ══════════════════════════════════════════════════════════════
# Task E – HubSpot Sync
# ══════════════════════════════════════════════════════════════
class TaskERequest(BaseModel):
    tenant_slug: str = "default"
    company_name: str
    cnpj: str
    domain: Optional[str] = None
    invoices_validated: int = 0
    exceptions_count: int = 0
    deal_value: Optional[str] = None
    async_mode: bool = False


@router.post("/hubspot-sync")
def trigger_task_e(req: TaskERequest, db: Session = Depends(get_db)):
    tid = _tenant_id(db, req.tenant_slug)
    kwargs = dict(
        tenant_id=tid,
        tenant_slug=req.tenant_slug,
        company_name=req.company_name,
        cnpj=req.cnpj,
        domain=req.domain,
        invoices_validated=req.invoices_validated,
        exceptions_count=req.exceptions_count,
        deal_value=req.deal_value,
    )
    if req.async_mode:
        r = task_e_hubspot_sync.delay(**kwargs)
        return {"task_id": r.id, "status": "QUEUED"}
    return task_e_hubspot_sync(**kwargs)
