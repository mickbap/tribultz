"""Task H — Processar arquivo SPED Fiscal e validar catálogo CBS/IBS."""

from __future__ import annotations

import csv
import io
import logging
from decimal import Decimal
from typing import Any

from app.celery_app import celery
from app.tools.postgres_tool import insert_audit_log, job_status_update
from app.services.sped_parser import parse as parse_sped

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")

# Alíquotas padrão 2026 (fallback quando NCM não consta na tabela)
CBS_DEFAULT = Decimal("0.0088")
IBS_DEFAULT = Decimal("0.0177")

# NCMs com redução a zero (simplificado — motor real consulta DB)
NCM_ZERO_RATED = {
    "01012100", "01012900",  # cavalos
    "02011000", "02012000", "02013000",  # carnes bovinas
    "04011000", "04012000", "04013000",  # leite
    "10061000", "10062000", "10063000", "10064000",  # arroz
    "10011100", "10011900",  # trigo
}


def _validate_produtos(produtos: list[dict], db_rules: dict) -> list[dict]:
    """Valida cada produto do 0200 contra regras CBS/IBS. Retorna lista com status."""
    results = []
    for p in produtos:
        ncm = p.get("ncm", "").replace(".", "").replace("-", "").strip()
        cest = p.get("cest", "").strip()

        flags: list[str] = []

        # Regra: NCM obrigatório
        if not ncm or len(ncm) not in (8,):
            flags.append("NCM_AUSENTE_OU_INVALIDO")

        # Regra: alíquota CBS/IBS por NCM
        ncm8 = ncm[:8] if len(ncm) >= 8 else ncm
        if ncm8 in NCM_ZERO_RATED:
            cbs_rate = Decimal("0")
            ibs_rate = Decimal("0")
        else:
            rule = db_rules.get(ncm8, {})
            cbs_rate = Decimal(str(rule.get("cbs", CBS_DEFAULT)))
            ibs_rate = Decimal(str(rule.get("ibs", IBS_DEFAULT)))

        # CEST obrigatório para substituição tributária (simplificado: tipo_item 04/05)
        tipo = p.get("tipo_item", "")
        if tipo in ("04", "05") and not cest:
            flags.append("CEST_OBRIGATORIO")

        status = "OK" if not flags else "DIVERGENTE"
        results.append({
            **p,
            "status":   status,
            "flags":    flags,
            "cbs_rate": str(cbs_rate),
            "ibs_rate": str(ibs_rate),
        })
    return results


def _generate_csv(produtos_validados: list[dict]) -> str:
    """Gera CSV ERP-ready com resultados da validação."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["cod_item", "descr", "ncm", "cest", "unid", "status", "flags", "cbs_rate", "ibs_rate"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for p in produtos_validados:
        row = dict(p)
        row["flags"] = "; ".join(p.get("flags", []))
        writer.writerow(row)
    return buf.getvalue()


@celery.task(name="task_h_process_sped", bind=True, max_retries=2)
def task_h_process_sped(
    self,
    tenant_id: str,
    sped_run_id: str,
    storage_key: str,
    original_filename: str,
    transaction_id: str | None = None,
) -> dict[str, Any]:
    """
    1. Baixa arquivo SPED do S3
    2. Parseia blocos 0000, 0200, C100, C170, C190
    3. Valida cada produto contra regras CBS/IBS
    4. Atualiza sped_ingestion_runs + jobs
    5. Retorna resultado com CSV inline
    """
    task_id = str(self.request.id) if self.request and self.request.id else ""
    if task_id:
        job_status_update(job_id=task_id, status="RUNNING", transaction_id=transaction_id)

    _update_run_status(sped_run_id, "RUNNING")

    try:
        # 1. Download do S3
        content = _download_s3(storage_key)

        # 2. Parse SPED
        parsed = parse_sped(content)
        produtos = parsed["produtos"]
        nfs      = parsed["nfs"]

        # 3. Validação (sem DB de NCMs por ora — usa defaults)
        produtos_validados = _validate_produtos(produtos, db_rules={})

        total       = len(produtos_validados)
        conformes   = sum(1 for p in produtos_validados if p["status"] == "OK")
        divergentes = total - conformes
        score_pct   = round(conformes / total * 100, 2) if total else 0.0

        # 4. Gerar CSV
        csv_content = _generate_csv(produtos_validados)

        result: dict[str, Any] = {
            "sped_run_id":   sped_run_id,
            "empresa":       parsed["empresa"],
            "periodo":       {
                "ini": parsed["periodo"]["ini"].isoformat() if parsed["periodo"].get("ini") else None,
                "fim": parsed["periodo"]["fim"].isoformat() if parsed["periodo"].get("fim") else None,
            },
            "total_produtos":       total,
            "produtos_conformes":   conformes,
            "produtos_divergentes": divergentes,
            "score_pct":            score_pct,
            "total_nfs":            len(nfs),
            "erros_parse":          parsed["erros_parse"],
            "produtos":             produtos_validados,
            "csv":                  csv_content,
        }

        # 5. Atualizar sped_ingestion_runs
        _update_run_result(sped_run_id, result, "SUCCESS")

        # 6. Audit log
        audit = insert_audit_log(
            tenant_id=tenant_id,
            action="sped_validation_success",
            entity_type="sped_run",
            entity_id=sped_run_id,
            payload={"total_produtos": total, "score_pct": score_pct, "divergentes": divergentes},
            transaction_id=transaction_id,
        )
        result["audit_id"] = audit["id"]

        if task_id:
            # Remove CSV do result do job (muito grande para JSONB do jobs.result)
            job_result = {k: v for k, v in result.items() if k != "csv"}
            job_result["csv_available"] = True
            job_status_update(job_id=task_id, status="SUCCESS", result=job_result, transaction_id=transaction_id)

        logger.info("Task H [%s] sped_run=%s score=%.1f%%", tenant_id[:8], sped_run_id[:8], score_pct)
        return result

    except Exception as exc:
        _update_run_status(sped_run_id, "FAILED")
        if task_id:
            job_status_update(job_id=task_id, status="FAILED", error_message=str(exc), transaction_id=transaction_id)
        raise


# ── Helpers ───────────────────────────────────────────────────────────────────

def _download_s3(storage_key: str) -> bytes:
    import boto3
    from botocore.config import Config as BotoConfig
    from app.config import settings

    cfg = BotoConfig(signature_version="s3v4", s3={"addressing_style": "path" if settings.S3_FORCE_PATH_STYLE else "virtual"})
    client = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        config=cfg,
        region_name=settings.S3_REGION,
    )
    obj = client.get_object(Bucket=settings.S3_BUCKET, Key=storage_key)
    return obj["Body"].read()


def _update_run_status(run_id: str, status: str) -> None:
    from app.database import SessionLocal
    from sqlalchemy import text
    with SessionLocal() as db:
        db.execute(
            text("UPDATE sped_ingestion_runs SET status = :s, updated_at = now() WHERE id = CAST(:id AS uuid)"),
            {"s": status, "id": run_id},
        )
        db.commit()


def _update_run_result(run_id: str, result: dict, status: str) -> None:
    from app.database import SessionLocal
    from sqlalchemy import text
    r = result
    with SessionLocal() as db:
        db.execute(
            text("""
                UPDATE sped_ingestion_runs SET
                    status               = :status,
                    total_produtos       = :total,
                    produtos_conformes   = :conformes,
                    produtos_divergentes = :divergentes,
                    cnpj_empresa         = :cnpj,
                    nome_empresa         = :nome,
                    periodo_ini          = CAST(:p_ini AS date),
                    periodo_fim          = CAST(:p_fim AS date),
                    updated_at           = now()
                WHERE id = CAST(:id AS uuid)
            """),
            {
                "status":     status,
                "total":      r.get("total_produtos", 0),
                "conformes":  r.get("produtos_conformes", 0),
                "divergentes": r.get("produtos_divergentes", 0),
                "cnpj":       r.get("empresa", {}).get("cnpj"),
                "nome":       r.get("empresa", {}).get("nome"),
                "p_ini":      r.get("periodo", {}).get("ini"),
                "p_fim":      r.get("periodo", {}).get("fim"),
                "id":         run_id,
            },
        )
        db.commit()
