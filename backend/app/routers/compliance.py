"""Compliance Score — índice CBS/IBS por tenant.

GET /api/v1/compliance/score         — score do período (default: mês atual)
GET /api/v1/compliance/score/history — histórico dos últimos 12 meses
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ComplianceScore(BaseModel):
    tenant_id: str
    period: str
    score_pct: float
    nfs_ok: int
    nfs_total: int
    findings_error: int
    findings_warning: int
    findings_info: int
    credit_at_risk: float
    computed_at: datetime


class ComplianceHistory(BaseModel):
    period: str
    score_pct: float
    nfs_total: int
    findings_error: int
    credit_at_risk: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_score_realtime(tenant_id: str, period: str, db: Session) -> dict:
    """Calcula o score em tempo real a partir dos jobs do período."""
    year, month = period.split("-")
    period_start = f"{year}-{month}-01"
    # Último dia do mês via truncagem
    rows = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'SUCCESS') AS nfs_ok,
                COUNT(*) AS nfs_total
            FROM jobs
            WHERE tenant_id = CAST(:tid AS uuid)
              AND job_type IN ('validate_xml', 'task_a_validate_cbs_ibs', 'sped_validation')
              AND created_at >= :start::date
              AND created_at < (:start::date + INTERVAL '1 month')
        """),
        {"tid": tenant_id, "start": period_start},
    ).mappings().fetchone()

    nfs_ok    = int((rows or {}).get("nfs_ok", 0) or 0)
    nfs_total = int((rows or {}).get("nfs_total", 0) or 0)

    # Findings do período
    findings = db.execute(
        text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE result->>'status' IN ('FAIL','FAILED')
                    OR (result->'findings') IS NOT NULL
                ) AS with_findings
            FROM jobs
            WHERE tenant_id = CAST(:tid AS uuid)
              AND job_type IN ('validate_xml', 'task_a_validate_cbs_ibs')
              AND created_at >= :start::date
              AND created_at < (:start::date + INTERVAL '1 month')
        """),
        {"tid": tenant_id, "start": period_start},
    ).mappings().fetchone()

    findings_error = int((findings or {}).get("with_findings", 0) or 0)
    score_pct = round(nfs_ok / nfs_total * 100, 2) if nfs_total else 0.0

    return {
        "tenant_id":       tenant_id,
        "period":          period,
        "score_pct":       score_pct,
        "nfs_ok":          nfs_ok,
        "nfs_total":       nfs_total,
        "findings_error":  findings_error,
        "findings_warning": 0,
        "findings_info":   0,
        "credit_at_risk":  0.0,
        "computed_at":     datetime.now(timezone.utc),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/score",
    response_model=ComplianceScore,
    summary="Score de conformidade CBS/IBS do período",
)
def get_score(
    period: Optional[str] = Query(None, description="Período YYYY-MM (default: mês atual)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    now = datetime.now(timezone.utc)
    target = period or f"{now.year}-{now.month:02d}"

    # Tenta buscar score pré-calculado
    row = db.execute(
        text("""
            SELECT tenant_id::text, period, score_pct, nfs_ok, nfs_total,
                   findings_error, findings_warning, findings_info,
                   credit_at_risk, computed_at
            FROM compliance_scores
            WHERE tenant_id = CAST(:tid AS uuid) AND period = :p
        """),
        {"tid": str(current_user.tenant_id), "p": target},
    ).mappings().fetchone()

    if row:
        return dict(row)

    # Fallback: calcular em tempo real (mês atual)
    return _compute_score_realtime(str(current_user.tenant_id), target, db)


@router.get(
    "/score/history",
    response_model=list[ComplianceHistory],
    summary="Histórico de conformidade — últimos 12 meses",
)
def get_score_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    rows = db.execute(
        text("""
            SELECT period, score_pct, nfs_total, findings_error, credit_at_risk
            FROM compliance_scores
            WHERE tenant_id = CAST(:tid AS uuid)
            ORDER BY period DESC
            LIMIT 12
        """),
        {"tid": str(current_user.tenant_id)},
    ).mappings().all()

    if rows:
        return [dict(r) for r in rows]

    # Sem histórico — retorna mês atual calculado em tempo real
    now = datetime.now(timezone.utc)
    current = _compute_score_realtime(
        str(current_user.tenant_id),
        f"{now.year}-{now.month:02d}",
        db,
    )
    return [{
        "period":         current["period"],
        "score_pct":      current["score_pct"],
        "nfs_total":      current["nfs_total"],
        "findings_error": current["findings_error"],
        "credit_at_risk": current["credit_at_risk"],
    }]
