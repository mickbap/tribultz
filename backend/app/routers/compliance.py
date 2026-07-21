"""Compliance Score — índice CBS/IBS por tenant.

GET /api/v1/compliance/score         — score do período (default: mês atual)
GET /api/v1/compliance/score/history — histórico dos últimos 12 meses
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])

# Job types cujo `result` tem o formato plano `{"findings": [...]}` usado pela
# agregação de risk-patterns. SPED (`sped_validation`) guarda achados em
# `result.produtos`, formato diferente — fica de fora, não quebra a query
# (o filtro job_type já exclui, e o guard jsonb_typeof abaixo é redundância
# defensiva contra qualquer job_type futuro com `result` sem findings).
_RISK_PATTERN_JOB_TYPES = ("validate_xml", "task_a_validate_cbs_ibs")


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


class RiskPatternRule(BaseModel):
    rule_id: str
    severity: str
    count: int


class RiskPatternDay(BaseModel):
    date: str
    fatal: int
    warning: int
    alert: int


class RiskPatternReport(BaseModel):
    period_days: int
    top_rules: list[RiskPatternRule]
    daily_trend: list[RiskPatternDay]


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
              AND created_at >= CAST(:start AS date)
              AND created_at < (CAST(:start AS date) + INTERVAL '1 month')
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
              AND created_at >= CAST(:start AS date)
              AND created_at < (CAST(:start AS date) + INTERVAL '1 month')
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


@router.get(
    "/risk-patterns",
    response_model=RiskPatternReport,
    summary="Padrão de risco agregado — findings recorrentes por regra/severidade no período",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def get_risk_patterns(
    days: int = Query(30, ge=1, le=365, description="Janela de dias pra trás (default: 30)"),
    top_n: int = Query(10, ge=1, le=50, description="Quantidade de regras no ranking"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Gap 4 vs. TOTVS (#442) — equivalente ao add-on "Inteligência Fiscal by
    IOB": cruza findings entre documentos/período pra achar padrão de risco
    recorrente, em vez de validar documento a documento (1:1). Agrega sobre
    `jobs.result->'findings'` já persistido — não requer mudança no motor.

    Substitui a agregação client-side do dashboard (`topRules`/`trendLast7Days`
    em page.tsx), que só olhava os últimos 50 jobs sem filtro de data —
    sub-reportava para qualquer tenant com mais volume que isso no período.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tenant_id = str(current_user.tenant_id)
    job_types = list(_RISK_PATTERN_JOB_TYPES)

    top_rows = db.execute(
        text("""
            SELECT
                f.value->>'rule_id' AS rule_id,
                COALESCE(f.value->>'severity', 'UNKNOWN') AS severity,
                COUNT(*) AS cnt
            FROM jobs j
            CROSS JOIN LATERAL jsonb_array_elements(j.result->'findings') AS f
            WHERE j.tenant_id = CAST(:tid AS uuid)
              AND j.job_type = ANY(:job_types)
              AND j.created_at >= :since
              AND jsonb_typeof(j.result->'findings') = 'array'
            GROUP BY 1, 2
            ORDER BY cnt DESC
            LIMIT :top_n
        """),
        {"tid": tenant_id, "job_types": job_types, "since": since, "top_n": top_n},
    ).mappings().all()

    trend_rows = db.execute(
        text("""
            SELECT
                (j.created_at AT TIME ZONE 'UTC')::date AS day,
                COALESCE(f.value->>'severity', 'UNKNOWN') AS severity,
                COUNT(*) AS cnt
            FROM jobs j
            CROSS JOIN LATERAL jsonb_array_elements(j.result->'findings') AS f
            WHERE j.tenant_id = CAST(:tid AS uuid)
              AND j.job_type = ANY(:job_types)
              AND j.created_at >= :since
              AND jsonb_typeof(j.result->'findings') = 'array'
            GROUP BY 1, 2
            ORDER BY 1
        """),
        {"tid": tenant_id, "job_types": job_types, "since": since},
    ).mappings().all()

    by_day: dict[str, dict[str, int]] = {}
    for row in trend_rows:
        day = row["day"].isoformat()
        bucket = by_day.setdefault(day, {"fatal": 0, "warning": 0, "alert": 0})
        sev = str(row["severity"]).lower()
        if sev in bucket:
            bucket[sev] += int(row["cnt"])

    return {
        "period_days": days,
        "top_rules": [
            {"rule_id": r["rule_id"], "severity": r["severity"], "count": int(r["cnt"])}
            for r in top_rows
        ],
        "daily_trend": [
            {"date": day, **counts} for day, counts in sorted(by_day.items())
        ],
    }
