"""Task I — Calcular Compliance Score mensal por tenant e sincronizar cClassTrib."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="compliance.compute_monthly_scores", bind=False)
def compute_monthly_scores() -> dict:
    """Calcula o Compliance Score do mês anterior para todos os tenants com jobs."""
    from app.database import SessionLocal
    from sqlalchemy import text

    now = datetime.now(timezone.utc)
    # Score do mês anterior
    if now.month == 1:
        year, month = now.year - 1, 12
    else:
        year, month = now.year, now.month - 1
    period = f"{year}-{month:02d}"
    period_start = f"{year}-{month:02d}-01"

    processed = 0
    with SessionLocal() as db:
        # Todos os tenants com jobs no período
        tenants = db.execute(
            text("""
                SELECT DISTINCT tenant_id::text
                FROM jobs
                WHERE created_at >= CAST(:start AS date)
                  AND created_at < (CAST(:start AS date) + INTERVAL '1 month')
                  AND job_type IN ('validate_xml', 'task_a_validate_cbs_ibs', 'sped_validation')
            """),
            {"start": period_start},
        ).scalars().all()

        for tenant_id in tenants:
            _upsert_score(db, tenant_id, period, period_start)
            processed += 1

        db.commit()

    logger.info("compliance.compute_monthly_scores period=%s tenants=%d", period, processed)
    return {"period": period, "tenants_processed": processed}


@celery.task(name="classtrib.sync_svrs", bind=False)
def sync_classtrib_svrs() -> dict:
    """Sincroniza tabela cClassTrib com a API SVRS. Roda semanalmente.

    A API SVRS exige credenciais institucionais (retorna 403 sem autenticação).
    Enquanto não configuradas, mantém os dados da migration 0018
    (regulamentos 30/abr/2026). Quando as credenciais forem obtidas, adicionar
    o header Authorization abaixo.
    """
    from app.database import SessionLocal
    from sqlalchemy import text

    SVRS_URL = "https://cff.svrs.rs.gov.br/api/v1/consultas/classTrib"
    HEADERS = {
        "User-Agent": "Tribultz/1.0 (contato@tribultz.com.br)",
        "Accept": "application/json",
    }

    try:
        import httpx
        with httpx.Client(timeout=30, headers=HEADERS) as client:
            resp = client.get(SVRS_URL)

        if resp.status_code == 403:
            logger.warning(
                "classtrib.sync_svrs: SVRS retornou 403 — credenciais necessárias. "
                "Dados locais (migration 0018) permanecem válidos."
            )
            return {"synced": 0, "reason": "svrs_auth_required", "status_code": 403}

        if resp.status_code == 404:
            logger.warning("classtrib.sync_svrs: endpoint SVRS não encontrado (404).")
            return {"synced": 0, "reason": "endpoint_not_found", "status_code": 404}

        resp.raise_for_status()
        items = resp.json()

    except httpx.HTTPStatusError as exc:
        logger.warning("classtrib.sync_svrs: HTTP %s — %s", exc.response.status_code, exc)
        return {"synced": 0, "error": str(exc), "status_code": exc.response.status_code}
    except Exception as exc:  # noqa: BLE001
        logger.warning("classtrib.sync_svrs: falha de rede (%s) — mantendo dados locais", exc)
        return {"synced": 0, "error": str(exc)}

    synced = 0
    with SessionLocal() as db:
        for item in items if isinstance(items, list) else []:
            codigo = (item.get("codigo") or item.get("code") or "").strip()
            descricao = (item.get("descricao") or item.get("description") or "").strip()
            if not codigo:
                continue
            db.execute(
                text("""
                    INSERT INTO cclass_trib_items
                        (codigo, descricao, p_cbs, p_ibs, regime_especial, vigencia_ini, synced_at, is_active)
                    VALUES (:c, :d, :cbs, :ibs, :regime, :vi, now(), TRUE)
                    ON CONFLICT (codigo) DO UPDATE SET
                        descricao       = EXCLUDED.descricao,
                        p_cbs           = EXCLUDED.p_cbs,
                        p_ibs           = EXCLUDED.p_ibs,
                        regime_especial = EXCLUDED.regime_especial,
                        vigencia_ini    = EXCLUDED.vigencia_ini,
                        synced_at       = now(),
                        is_active       = TRUE
                """),
                {
                    "c":      codigo,
                    "d":      descricao,
                    "cbs":    float(item.get("aliquotaCBS", item.get("p_cbs", 0.88))),
                    "ibs":    float(item.get("aliquotaIBS", item.get("p_ibs", 0.176))),
                    "regime": item.get("regimeEspecial", item.get("regime_especial")),
                    "vi":     item.get("vigenciaIni", item.get("vigencia_ini", "2026-01-01")),
                },
            )
            synced += 1
        db.commit()

    logger.info("classtrib.sync_svrs synced=%d items from SVRS", synced)
    return {"synced": synced}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_score(db, tenant_id: str, period: str, period_start: str) -> None:
    from sqlalchemy import text

    row = db.execute(
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

    nfs_ok    = int((row or {}).get("nfs_ok", 0) or 0)
    nfs_total = int((row or {}).get("nfs_total", 0) or 0)
    score_pct = round(nfs_ok / nfs_total * 100, 2) if nfs_total else 0.0

    findings_row = db.execute(
        text("""
            SELECT COUNT(*) AS cnt
            FROM jobs
            WHERE tenant_id = CAST(:tid AS uuid)
              AND job_type IN ('validate_xml', 'task_a_validate_cbs_ibs')
              AND status = 'FAILED'
              AND created_at >= CAST(:start AS date)
              AND created_at < (CAST(:start AS date) + INTERVAL '1 month')
        """),
        {"tid": tenant_id, "start": period_start},
    ).scalar_one_or_none()

    db.execute(
        text("""
            INSERT INTO compliance_scores
                (tenant_id, period, score_pct, nfs_ok, nfs_total, findings_error, computed_at)
            VALUES
                (CAST(:tid AS uuid), :p, :score, :ok, :total, :err, now())
            ON CONFLICT (tenant_id, period) DO UPDATE SET
                score_pct      = EXCLUDED.score_pct,
                nfs_ok         = EXCLUDED.nfs_ok,
                nfs_total      = EXCLUDED.nfs_total,
                findings_error = EXCLUDED.findings_error,
                computed_at    = now()
        """),
        {
            "tid":   tenant_id,
            "p":     period,
            "score": score_pct,
            "ok":    nfs_ok,
            "total": nfs_total,
            "err":   int(findings_row or 0),
        },
    )
