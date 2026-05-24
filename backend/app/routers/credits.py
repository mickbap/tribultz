"""Credit Dashboard — saldo e fluxo de crédito IBS/CBS por período (LC 214).

Fase 1 (#258): visão agregada por período (mês/trimestre) derivada da tabela
`documents` + `split_payment_status` (introduzido pelo #169). Sem tabela nova.

GET /api/v1/credits/balance?period=month|quarter — série temporal de saldo
GET /api/v1/credits/export.csv?period=...        — mesmo dado em CSV auditável

Fluxo (LC 214 art. 22, não-cumulatividade plena):
  gerado      = confirmed + credit_released  (crédito efetivamente formalizado)
  apropriado  = credit_released              (crédito já utilizado/compensado)
  disponível  = confirmed                    (crédito formalizado e não utilizado)
  em_risco    = failed                       (crédito potencialmente perdido)

Fase 2 (futuro): drill-down por NF, PDF, IBS/CBS separados por NCM,
breakdown automático a partir de fiscal_metadata enriquecido.
"""

from __future__ import annotations

import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])

PeriodGranularity = Literal["month", "quarter"]


class CreditPeriodRow(BaseModel):
    period: str                # "2026-05" ou "2026-Q2"
    generated_count: int
    generated_total: str       # R$ (string p/ evitar perda de precisão)
    apropriated_count: int
    apropriated_total: str
    available_count: int
    available_total: str
    at_risk_count: int
    at_risk_total: str


class CreditBalanceResponse(BaseModel):
    period_type: PeriodGranularity
    periods: list[CreditPeriodRow]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _period_label(period_type: PeriodGranularity, bucket_iso: str) -> str:
    """bucket_iso vem do date_trunc — formata para 'YYYY-MM' ou 'YYYY-Qn'."""
    # bucket_iso ex: '2026-05-01' (month) ou '2026-04-01' (quarter start)
    year, month, _ = bucket_iso.split("-")[:3]
    if period_type == "month":
        return f"{year}-{month}"
    # quarter: month 1→Q1, 4→Q2, 7→Q3, 10→Q4
    q = (int(month) - 1) // 3 + 1
    return f"{year}-Q{q}"


def _compute_balance(
    db: Session,
    tenant_id: str,
    period_type: PeriodGranularity,
    months_back: int,
) -> list[CreditPeriodRow]:
    """Agrega documents.split_payment_status por bucket de tempo.

    Usa date_trunc + COALESCE para extrair credit_value de fiscal_metadata.
    """
    trunc_unit = "month" if period_type == "month" else "quarter"
    rows = db.execute(
        text(f"""
            SELECT
                date_trunc('{trunc_unit}', created_at)::date AS bucket,
                split_payment_status AS status,
                COUNT(*) AS cnt,
                COALESCE(SUM(
                    NULLIF(fiscal_metadata->>'credit_value', '')::numeric
                ), 0) AS total
            FROM documents
            WHERE tenant_id = CAST(:tid AS uuid)
              AND split_payment_status IS NOT NULL
              AND created_at >= (now() - (:months_back || ' months')::interval)
            GROUP BY bucket, split_payment_status
            ORDER BY bucket DESC
        """),
        {"tid": tenant_id, "months_back": months_back},
    ).mappings().all()

    # Agrupa por bucket
    buckets: dict[str, dict[str, dict[str, float]]] = {}
    for r in rows:
        bucket_iso = r["bucket"].isoformat()
        status = r["status"]
        buckets.setdefault(bucket_iso, {})[status] = {
            "count": int(r["cnt"] or 0),
            "total": float(r["total"] or 0),
        }

    out: list[CreditPeriodRow] = []
    for bucket_iso in sorted(buckets.keys(), reverse=True):
        by_status = buckets[bucket_iso]
        confirmed = by_status.get("confirmed", {"count": 0, "total": 0.0})
        released = by_status.get("credit_released", {"count": 0, "total": 0.0})
        failed = by_status.get("failed", {"count": 0, "total": 0.0})

        gen_count = int(confirmed["count"] + released["count"])
        gen_total = float(confirmed["total"] + released["total"])

        out.append(CreditPeriodRow(
            period=_period_label(period_type, bucket_iso),
            generated_count=gen_count,
            generated_total=f"{gen_total:.2f}",
            apropriated_count=int(released["count"]),
            apropriated_total=f"{float(released['total']):.2f}",
            available_count=int(confirmed["count"]),
            available_total=f"{float(confirmed['total']):.2f}",
            at_risk_count=int(failed["count"]),
            at_risk_total=f"{float(failed['total']):.2f}",
        ))

    return out


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/balance",
    response_model=CreditBalanceResponse,
    summary="Saldo de crédito IBS/CBS por período",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def get_credit_balance(
    period: PeriodGranularity = Query("month", description="Granularidade: month | quarter"),
    months_back: int = Query(12, ge=1, le=36, description="Janela em meses"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreditBalanceResponse:
    periods = _compute_balance(db, str(current_user.tenant_id), period, months_back)
    return CreditBalanceResponse(period_type=period, periods=periods)


@router.get(
    "/export.csv",
    summary="Exporta saldo de crédito em CSV auditável",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def export_credit_balance_csv(
    period: PeriodGranularity = Query("month"),
    months_back: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    rows = _compute_balance(db, str(current_user.tenant_id), period, months_back)

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")  # ; para compatibilidade Excel pt-BR
    writer.writerow([
        "PERIODO",
        "GERADO_QTD", "GERADO_TOTAL_BRL",
        "APROPRIADO_QTD", "APROPRIADO_TOTAL_BRL",
        "DISPONIVEL_QTD", "DISPONIVEL_TOTAL_BRL",
        "EM_RISCO_QTD", "EM_RISCO_TOTAL_BRL",
    ])
    for r in rows:
        writer.writerow([
            r.period,
            r.generated_count, r.generated_total,
            r.apropriated_count, r.apropriated_total,
            r.available_count, r.available_total,
            r.at_risk_count, r.at_risk_total,
        ])

    buf.seek(0)
    filename = f"credito-ibs-cbs-{period}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
