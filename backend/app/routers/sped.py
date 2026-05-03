"""SPED Fiscal ingestion — upload e validação de catálogo CBS/IBS.

POST /api/v1/sped/upload   — recebe arquivo .txt SPED, dispara task assíncrona
GET  /api/v1/sped/{run_id} — status + resultado da ingestão
"""

from __future__ import annotations

import json
import uuid as _uuid
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.database import get_db
from app.models.auth import User
from app.tools import s3_tool
from app.tools.postgres_tool import job_create

router = APIRouter(prefix="/api/v1/sped", tags=["sped"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


# ── Schemas ───────────────────────────────────────────────────────────────────

class SpedRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: Optional[UUID]
    original_filename: str
    file_size: Optional[int]
    status: str
    total_produtos: int
    produtos_conformes: int
    produtos_divergentes: int
    cnpj_empresa: Optional[str]
    nome_empresa: Optional[str]
    periodo_ini: Optional[datetime]
    periodo_fim: Optional[datetime]
    created_at: datetime


class SpedUploadResponse(BaseModel):
    sped_run_id: UUID
    job_id: UUID
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=SpedUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enviar arquivo SPED Fiscal para validação",
    description=(
        "Aceita arquivo .txt SPED Fiscal (EFD-ICMS/IPI) até 100 MB. "
        "Dispara processamento assíncrono — acompanhe o progresso via GET /sped/{run_id}."
    ),
)
async def upload_sped(
    file: UploadFile = File(..., description="Arquivo SPED Fiscal (.txt)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _plan: User = Depends(require_plan("empresarial", "contador")),
) -> SpedUploadResponse:

    if not file.filename or not file.filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Arquivo deve ser .txt (formato SPED Fiscal).",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande. Máximo: {MAX_FILE_SIZE // 1024 // 1024} MB.",
        )
    if len(content) == 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Arquivo vazio.")

    # Upload para S3
    run_id = str(_uuid.uuid4())
    storage_key = f"sped/{current_user.tenant_id}/{run_id}/{file.filename}"
    try:
        s3_tool.put_object(key=storage_key, data=content, content_type="text/plain")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Falha ao armazenar arquivo: {exc}",
        ) from exc

    # Criar registro sped_ingestion_runs
    db.execute(
        text("""
            INSERT INTO sped_ingestion_runs
                (id, tenant_id, original_filename, file_size, storage_key, status)
            VALUES
                (CAST(:id AS uuid), CAST(:tenant_id AS uuid), :filename, :file_size, :storage_key, 'PENDING')
        """),
        {
            "id":          run_id,
            "tenant_id":   str(current_user.tenant_id),
            "filename":    file.filename,
            "file_size":   len(content),
            "storage_key": storage_key,
        },
    )
    db.commit()

    # Criar job
    job_id_str = str(_uuid.uuid4())
    job_create(
        job_id=job_id_str,
        tenant_id=str(current_user.tenant_id),
        job_type="sped_validation",
        payload={
            "sped_run_id":       run_id,
            "storage_key":       storage_key,
            "original_filename": file.filename,
            "file_size":         len(content),
        },
    )
    job_id = job_id_str

    # Vincular job ao run
    db.execute(
        text("UPDATE sped_ingestion_runs SET job_id = CAST(:job_id AS uuid) WHERE id = CAST(:id AS uuid)"),
        {"job_id": job_id, "id": run_id},
    )
    db.commit()

    # Disparar task Celery
    from app.tasks.task_h_sped import task_h_process_sped
    task_h_process_sped.apply_async(
        task_id=job_id,
        kwargs={
            "tenant_id":         str(current_user.tenant_id),
            "sped_run_id":       run_id,
            "storage_key":       storage_key,
            "original_filename": file.filename,
        },
    )

    return SpedUploadResponse(
        sped_run_id=UUID(run_id),
        job_id=UUID(job_id),
        message="Arquivo recebido. Processamento iniciado.",
    )


@router.get(
    "/{run_id}",
    response_model=SpedRunResponse,
    summary="Status e resultado da ingestão SPED",
)
def get_sped_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    row = db.execute(
        text("""
            SELECT id, job_id, original_filename, file_size, status,
                   total_produtos, produtos_conformes, produtos_divergentes,
                   cnpj_empresa, nome_empresa, periodo_ini, periodo_fim, created_at
            FROM sped_ingestion_runs
            WHERE id = CAST(:id AS uuid) AND tenant_id = CAST(:tid AS uuid)
        """),
        {"id": str(run_id), "tid": str(current_user.tenant_id)},
    ).mappings().fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestão não encontrada.")

    return dict(row)


@router.get(
    "/{run_id}/csv",
    response_class=PlainTextResponse,
    summary="Download do CSV de resultados (ERP-ready)",
)
def get_sped_csv(
    run_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> str:
    row = db.execute(
        text("""
            SELECT j.result
            FROM sped_ingestion_runs sr
            JOIN jobs j ON j.id = sr.job_id
            WHERE sr.id = CAST(:id AS uuid) AND sr.tenant_id = CAST(:tid AS uuid)
              AND sr.status = 'SUCCESS'
        """),
        {"id": str(run_id), "tid": str(current_user.tenant_id)},
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado não disponível ainda. Aguarde o processamento.",
        )

    result = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    csv_data = result.get("csv") or result.get("produtos", [])

    if isinstance(csv_data, list):
        # Regenerar CSV a partir dos produtos no result
        import csv as _csv
        import io
        buf = io.StringIO()
        if csv_data:
            writer = _csv.DictWriter(
                buf,
                fieldnames=["cod_item", "descr", "ncm", "cest", "unid", "status", "flags", "cbs_rate", "ibs_rate"],
                extrasaction="ignore",
            )
            writer.writeheader()
            for p in csv_data:
                row_data = dict(p)
                row_data["flags"] = "; ".join(p.get("flags", []))
                writer.writerow(row_data)
        return buf.getvalue()

    return str(csv_data)


@router.get(
    "/{run_id}/export/erp",
    summary="Exportar catálogo SPED para ERP (TOTVS, SAP, Omie, Linx, Genérico)",
    description=(
        "Gera arquivo de exportação no formato do ERP selecionado. "
        "Disponível quando o processamento estiver em status SUCCESS."
    ),
)
def export_sped_erp(
    run_id: UUID,
    format: Literal["totvs", "sap", "omie", "linx", "generic"] = Query(
        default="generic",
        description="Formato de exportação: totvs | sap | omie | linx | generic",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    from app.services.erp_export import generate as erp_generate

    row = db.execute(
        text("""
            SELECT j.result, sr.created_at
            FROM sped_ingestion_runs sr
            JOIN jobs j ON j.id = sr.job_id
            WHERE sr.id = CAST(:id AS uuid) AND sr.tenant_id = CAST(:tid AS uuid)
              AND sr.status = 'SUCCESS'
        """),
        {"id": str(run_id), "tid": str(current_user.tenant_id)},
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resultado não disponível. Aguarde o processamento ou verifique o status.",
        )

    result = row[0] if isinstance(row[0], dict) else json.loads(row[0])
    produtos = result.get("produtos", [])
    data_validacao = row[1].date().isoformat() if row[1] else None

    content, content_type, suffix = erp_generate(produtos, format, data_validacao)  # type: ignore[arg-type]
    filename = f"tribultz_sped_{str(run_id)[:8]}_{suffix}"

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
