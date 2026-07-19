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

Fase 2, parte 1 (#258): drill-down por NF integrado a este dashboard
(GET /documents, reaproveita SplitPaymentDoc/_to_doc de split_payment.py —
mesma fonte de dado, não duplica) + export PDF com a trilha auditável por
documento (GET /export.pdf).

Fase 2, parte 2 (#486, esta entrega): IBS e CBS reportados separadamente em
cada categoria do fluxo (gerado/apropriado/disponível/em_risco), lendo
`credit_value_ibs`/`credit_value_cbs` do `fiscal_metadata` (split_payment.py).
Tabela `credit_events` dedicada foi avaliada e **deliberadamente adiada** —
não existe hoje nenhuma fonte automática de evento discreto de crédito (nem
extração de vCBS/vIBS do XML, nem integração com a Nota Nacional — ver
Fase 2 de split_payment.py); todo o dado é entrada manual via
`PATCH /split-payment/status/{id}`. Um livro-razão de eventos sem uma fonte
real de eventos granulares seria estrutura vazia — construir quando a
integração com a Nota Nacional (que geraria eventos de verdade) existir.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Sequence
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import Tenant, User
from app.routers.split_payment import SplitPaymentDoc, _combined_credit_value, _to_doc

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])

PeriodGranularity = Literal["month", "quarter"]


class CreditPeriodRow(BaseModel):
    period: str                # "2026-05" ou "2026-Q2"
    generated_count: int
    generated_total: str       # R$ (string p/ evitar perda de precisão)
    generated_total_ibs: str   # #486 — quebra por tributo
    generated_total_cbs: str
    apropriated_count: int
    apropriated_total: str
    apropriated_total_ibs: str
    apropriated_total_cbs: str
    available_count: int
    available_total: str
    available_total_ibs: str
    available_total_cbs: str
    at_risk_count: int
    at_risk_total: str
    at_risk_total_ibs: str
    at_risk_total_cbs: str


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
    O total combinado usa `credit_value` legado se presente; senão soma
    `credit_value_ibs` + `credit_value_cbs` (#486) — mesma precedência de
    `split_payment.py::_combined_credit_value`, replicada em SQL para agregar
    sem trazer todas as linhas para Python.
    """
    trunc_unit = "month" if period_type == "month" else "quarter"
    rows = db.execute(
        text(f"""
            SELECT
                date_trunc('{trunc_unit}', created_at)::date AS bucket,
                split_payment_status AS status,
                COUNT(*) AS cnt,
                COALESCE(SUM(
                    COALESCE(
                        NULLIF(fiscal_metadata->>'credit_value', '')::numeric,
                        COALESCE(NULLIF(fiscal_metadata->>'credit_value_ibs', '')::numeric, 0)
                        + COALESCE(NULLIF(fiscal_metadata->>'credit_value_cbs', '')::numeric, 0)
                    )
                ), 0) AS total,
                COALESCE(SUM(NULLIF(fiscal_metadata->>'credit_value_ibs', '')::numeric), 0) AS total_ibs,
                COALESCE(SUM(NULLIF(fiscal_metadata->>'credit_value_cbs', '')::numeric), 0) AS total_cbs
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
            "total_ibs": float(r["total_ibs"] or 0),
            "total_cbs": float(r["total_cbs"] or 0),
        }

    _zero = {"count": 0, "total": 0.0, "total_ibs": 0.0, "total_cbs": 0.0}

    out: list[CreditPeriodRow] = []
    for bucket_iso in sorted(buckets.keys(), reverse=True):
        by_status = buckets[bucket_iso]
        confirmed = by_status.get("confirmed", dict(_zero))
        released = by_status.get("credit_released", dict(_zero))
        failed = by_status.get("failed", dict(_zero))

        gen_count = int(confirmed["count"] + released["count"])
        gen_total = float(confirmed["total"] + released["total"])
        gen_ibs = float(confirmed["total_ibs"] + released["total_ibs"])
        gen_cbs = float(confirmed["total_cbs"] + released["total_cbs"])

        out.append(CreditPeriodRow(
            period=_period_label(period_type, bucket_iso),
            generated_count=gen_count,
            generated_total=f"{gen_total:.2f}",
            generated_total_ibs=f"{gen_ibs:.2f}",
            generated_total_cbs=f"{gen_cbs:.2f}",
            apropriated_count=int(released["count"]),
            apropriated_total=f"{float(released['total']):.2f}",
            apropriated_total_ibs=f"{float(released['total_ibs']):.2f}",
            apropriated_total_cbs=f"{float(released['total_cbs']):.2f}",
            available_count=int(confirmed["count"]),
            available_total=f"{float(confirmed['total']):.2f}",
            available_total_ibs=f"{float(confirmed['total_ibs']):.2f}",
            available_total_cbs=f"{float(confirmed['total_cbs']):.2f}",
            at_risk_count=int(failed["count"]),
            at_risk_total=f"{float(failed['total']):.2f}",
            at_risk_total_ibs=f"{float(failed['total_ibs']):.2f}",
            at_risk_total_cbs=f"{float(failed['total_cbs']):.2f}",
        ))

    return out


def _documents_with_bucket(
    db: Session,
    tenant_id: str,
    period_type: PeriodGranularity,
    months_back: int,
) -> Sequence[Any]:
    """Documentos rastreados no Split Payment, com o bucket de período de cada
    um — base tanto do drill-down (`GET /documents`) quanto do PDF auditável.
    Reaproveita a mesma janela/condição de `_compute_balance`, só sem agregar.
    """
    trunc_unit = "month" if period_type == "month" else "quarter"
    return db.execute(
        text(f"""
            SELECT
                id, original_filename, doc_type, fiscal_metadata,
                split_payment_status, created_at,
                date_trunc('{trunc_unit}', created_at)::date AS bucket
            FROM documents
            WHERE tenant_id = CAST(:tid AS uuid)
              AND split_payment_status IS NOT NULL
              AND created_at >= (now() - (:months_back || ' months')::interval)
            ORDER BY created_at DESC
        """),
        {"tid": tenant_id, "months_back": months_back},
    ).all()


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
        "GERADO_QTD", "GERADO_TOTAL_BRL", "GERADO_IBS_BRL", "GERADO_CBS_BRL",
        "APROPRIADO_QTD", "APROPRIADO_TOTAL_BRL", "APROPRIADO_IBS_BRL", "APROPRIADO_CBS_BRL",
        "DISPONIVEL_QTD", "DISPONIVEL_TOTAL_BRL", "DISPONIVEL_IBS_BRL", "DISPONIVEL_CBS_BRL",
        "EM_RISCO_QTD", "EM_RISCO_TOTAL_BRL", "EM_RISCO_IBS_BRL", "EM_RISCO_CBS_BRL",
    ])
    for r in rows:
        writer.writerow([
            r.period,
            r.generated_count, r.generated_total, r.generated_total_ibs, r.generated_total_cbs,
            r.apropriated_count, r.apropriated_total, r.apropriated_total_ibs, r.apropriated_total_cbs,
            r.available_count, r.available_total, r.available_total_ibs, r.available_total_cbs,
            r.at_risk_count, r.at_risk_total, r.at_risk_total_ibs, r.at_risk_total_cbs,
        ])

    buf.seek(0)
    filename = f"credito-ibs-cbs-{period}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/documents",
    response_model=list[SplitPaymentDoc],
    summary="Documentos (NFs) que compõem o crédito de um período — drill-down",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def get_credit_documents(
    period: str = Query(..., description="Rótulo do período, ex.: '2026-07' (mês) ou '2026-Q3' (trimestre)"),
    period_type: PeriodGranularity = Query("month"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SplitPaymentDoc]:
    """Rastreabilidade por NF (#258): qual documento compõe o saldo de um
    período específico da tela `/credits`. Reaproveita `_to_doc`/`SplitPaymentDoc`
    de `split_payment.py` — mesma fonte de dado, não duplica.
    """
    rows = _documents_with_bucket(db, str(current_user.tenant_id), period_type, months_back=36)
    matching = [r for r in rows if _period_label(period_type, r.bucket.isoformat()) == period]
    return [_to_doc(r) for r in matching]


@router.get(
    "/export.pdf",
    summary="Exporta saldo de crédito em PDF com trilha auditável por NF",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def export_credit_balance_pdf(
    period: PeriodGranularity = Query("month"),
    months_back: int = Query(12, ge=1, le=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    balance_rows = _compute_balance(db, str(current_user.tenant_id), period, months_back)
    doc_rows = _documents_with_bucket(db, str(current_user.tenant_id), period, months_back)

    docs_by_period: dict[str, list[dict[str, Any]]] = {}
    for r in doc_rows:
        label = _period_label(period, r.bucket.isoformat())
        fm = r.fiscal_metadata if isinstance(r.fiscal_metadata, dict) else {}
        docs_by_period.setdefault(label, []).append({
            "filename": r.original_filename or str(r.id)[:8],
            "doc_type": r.doc_type,
            "status": r.split_payment_status,
            "credit_value": _combined_credit_value(fm),
            "credit_value_ibs": fm.get("credit_value_ibs"),
            "credit_value_cbs": fm.get("credit_value_cbs"),
            "created_at": r.created_at.strftime("%d/%m/%Y") if r.created_at else "",
        })

    periods_payload = [
        {
            "period": row.period,
            "generated_count": row.generated_count,
            "generated_total": row.generated_total,
            "generated_total_ibs": row.generated_total_ibs,
            "generated_total_cbs": row.generated_total_cbs,
            "apropriated_total": row.apropriated_total,
            "available_total": row.available_total,
            "at_risk_total": row.at_risk_total,
            "documents": docs_by_period.get(row.period, []),
        }
        for row in balance_rows
    ]

    tenant = db.get(Tenant, current_user.tenant_id)
    from app.services.pdf_service import generate_credit_report_pdf

    result = generate_credit_report_pdf(
        company_name=cast(str, tenant.name) if tenant is not None else "",
        cnpj=cast(str, current_user.cnpj) if current_user.cnpj is not None else "",
        period_type=period,
        periods=periods_payload,
    )

    pdf_bytes = result["bytes"]
    content_type = "application/pdf"
    filename = f"credito-ibs-cbs-{period}.pdf"
    if pdf_bytes[:15] == b"<!DOCTYPE html>":
        content_type = "text/html; charset=utf-8"
        filename = f"credito-ibs-cbs-{period}.html"

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
