#!/usr/bin/env python3
"""Parser -> Normalização -> Consolidação -> upsert idempotente em prospect_orgs
(PO-2026-07-SALES-001, Fase 1; salvaguardas operacionais da Ordem Complementar).

Uso:
  cd backend && source .venv/bin/activate
  python ../tools/prospecting/ingest_cnpj_dump.py \\
      --dump-dir /caminho/para/dump/2026-07 --dump-reference 2026-07 \\
      --download-date 2026-07-01

--dump-dir deve conter os arquivos oficiais extraídos (Empresas*, Estabelecimentos*,
Simples*, Socios*, Municipios*), baixados de arquivos.receitafederal.gov.br — ver
README.md deste diretório para o passo a passo completo.

Salvaguardas (Ordem Complementar):
  - Pré-checagem de layout ANTES de qualquer parsing — aborta se o número de
    campos não bater com o esperado (item 2).
  - Guarda de sanidade de volume DEPOIS de consolidar, ANTES de escrever em
    prospect_orgs — aborta com erro explícito (nunca só warning) se as
    métricas fugirem dos limites configurados ou da última execução
    compatível (item 1).
  - Toda execução real (sucesso ou abortada) grava uma linha em
    prospect_ingestion_runs, com hash SHA-256 dos arquivos usados (item 2) —
    exceto em --dry-run, que não escreve nada em lugar nenhum.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.prospect_ingestion_run import ProspectIngestionRun  # noqa: E402
from app.models.prospect_org import ProspectOrg  # noqa: E402
from app.services.prospecting.consolidation import (  # noqa: E402
    TARGET_CNAES,
    ConsolidatedOrg,
    build_consolidated_orgs,
)
from app.services.prospecting.layout_check import (  # noqa: E402
    LayoutMismatchError,
    MalformedRowRatioError,
    check_malformed_ratio,
    compute_file_hashes,
    detect_layout_signature,
)
from app.services.prospecting.rf_parser import RowCounts  # noqa: E402
from app.services.prospecting.sanity import (  # noqa: E402
    IngestionMetrics,
    SanityCheckError,
    load_thresholds,
    validate_metrics,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("prospecting.ingest_cnpj_dump")

_UPSERT_COLUMNS = (
    "cnpj_matriz", "razao_social", "nome_fantasia", "porte", "opcao_mei",
    "opcao_simples", "capital_social", "situacao_cadastral", "data_situacao_cadastral",
    "data_inicio_atividade", "qtd_socios", "qtd_estabelecimentos", "uf",
    "municipio_codigo", "municipio_nome", "logradouro", "numero", "complemento",
    "bairro", "cep", "ddd_telefone1", "telefone1", "email", "email_domain",
    "email_domain_category", "email_type", "cnae_principal", "cnaes_secundarios",
    "source_dump_reference",
)


def _row_from_org(org: ConsolidatedOrg) -> dict:
    row = {"cnpj_basico": org.cnpj_basico}
    for col in _UPSERT_COLUMNS:
        row[col] = getattr(org, col)
    row["situacao_cadastral"] = str(org.situacao_cadastral)
    return row


def upsert_orgs(db, orgs: list[ConsolidatedOrg]) -> int:
    """Upsert idempotente via ON CONFLICT (cnpj_basico) DO UPDATE — seguro
    reexecutar após uma falha ou com um dump mensal atualizado."""
    if not orgs:
        return 0
    rows = [_row_from_org(o) for o in orgs]
    stmt = pg_insert(ProspectOrg).values(rows)
    update_cols = {col: getattr(stmt.excluded, col) for col in _UPSERT_COLUMNS}
    stmt = stmt.on_conflict_do_update(index_elements=["cnpj_basico"], set_=update_cols)
    db.execute(stmt)
    db.commit()
    return len(rows)


def _find_previous_metrics(db, target_cnaes_sorted: list[str]) -> IngestionMetrics | None:
    """Última execução bem-sucedida com o MESMO --target-cnaes — configs
    diferentes não são comparáveis entre si (Ordem Complementar, item 1)."""
    row = db.execute(
        select(ProspectIngestionRun)
        .where(
            ProspectIngestionRun.status == "completed",
            ProspectIngestionRun.target_cnaes == target_cnaes_sorted,
        )
        .order_by(ProspectIngestionRun.finished_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None
    return IngestionMetrics(
        total_estabelecimentos_scanned=row.total_estabelecimentos_scanned or 0,
        total_target_cnae_found=row.total_target_cnae_found or 0,
        total_ativas=row.total_ativas or 0,
        total_consolidated=row.total_consolidated or 0,
    )


def _record_run(
    db,
    *,
    dump_reference: str,
    target_cnaes_sorted: list[str],
    download_date: date,
    status: str,
    started_at: datetime,
    error_message: str | None = None,
    metrics: IngestionMetrics | None = None,
    tolerance_params: dict | None = None,
    file_count: int | None = None,
    files_sha256: dict | None = None,
    layout_signature: str | None = None,
) -> None:
    """Grava uma linha em prospect_ingestion_runs — append-only, sempre, tanto
    para sucesso quanto para abortos (item 8, auditoria completa)."""
    db.add(
        ProspectIngestionRun(
            dump_reference=dump_reference,
            target_cnaes=target_cnaes_sorted,
            download_date=download_date,
            status=status,
            error_message=error_message,
            total_estabelecimentos_scanned=metrics.total_estabelecimentos_scanned if metrics else None,
            total_target_cnae_found=metrics.total_target_cnae_found if metrics else None,
            total_ativas=metrics.total_ativas if metrics else None,
            total_consolidated=metrics.total_consolidated if metrics else None,
            tolerance_params=tolerance_params or {},
            file_count=file_count,
            files_sha256=files_sha256,
            layout_signature=layout_signature,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump-dir", required=True, type=Path, help="Diretório com os arquivos oficiais extraídos.")
    parser.add_argument("--dump-reference", required=True, help='Ex.: "2026-07" — vintage do dump.')
    parser.add_argument(
        "--download-date", required=True,
        help='Data em que o dump foi baixado, ISO (ex.: "2026-07-01") — não dá para '
             "inferir de forma confiável a partir do sistema de arquivos.",
    )
    parser.add_argument("--target-cnaes", default=",".join(sorted(TARGET_CNAES)))
    parser.add_argument("--dry-run", action="store_true", help="Só parseia e reporta contagens, não escreve em lugar nenhum.")
    parser.add_argument(
        "--sanity-thresholds-path", type=Path, default=None,
        help="Override de backend/app/data/prospecting/sanity_thresholds.yaml (usado pelos testes).",
    )
    args = parser.parse_args(argv)

    if not args.dump_dir.is_dir():
        parser.error(f"--dump-dir não é um diretório: {args.dump_dir}")
    try:
        download_date = date.fromisoformat(args.download_date)
    except ValueError:
        parser.error(f'--download-date inválido (use ISO, ex. "2026-07-01"): {args.download_date}')
        return 2  # inalcançável — parser.error já sai do processo; só para o type checker

    target_cnaes = frozenset(c.strip() for c in args.target_cnaes.split(",") if c.strip())
    target_cnaes_sorted = sorted(target_cnaes)
    started_at = datetime.now(timezone.utc)

    logger.info(
        "Iniciando ingestão: dump_dir=%s dump_reference=%s target_cnaes=%s",
        args.dump_dir, args.dump_reference, target_cnaes_sorted,
    )

    # ── Pré-checagem de layout — ANTES de processar qualquer linha (item 2) ──
    try:
        layout_signature = detect_layout_signature(args.dump_dir)
    except LayoutMismatchError as exc:
        logger.error("Layout incompatível — abortando antes de qualquer parsing: %s", exc)
        if not args.dry_run:
            db = SessionLocal()
            try:
                _record_run(
                    db, dump_reference=args.dump_reference, target_cnaes_sorted=target_cnaes_sorted,
                    download_date=download_date, status="aborted_layout_mismatch",
                    started_at=started_at, error_message=str(exc),
                )
            finally:
                db.close()
        return 1
    logger.info("Layout confirmado: %s", layout_signature)

    file_hashes = compute_file_hashes(args.dump_dir)
    logger.info("%d arquivos hasheados (proveniência)", len(file_hashes))

    thresholds = load_thresholds(args.sanity_thresholds_path)

    estab_counts = RowCounts()
    result = build_consolidated_orgs(
        args.dump_dir, dump_reference=args.dump_reference, target_cnaes=target_cnaes,
        estab_row_counts=estab_counts,
    )
    orgs = result.orgs
    logger.info(
        "%d organizações consolidadas (situação cadastral ativa, dedup por CNPJ básico)", len(orgs)
    )

    metrics = IngestionMetrics(
        total_estabelecimentos_scanned=result.metrics.total_estabelecimentos_scanned,
        total_target_cnae_found=result.metrics.total_target_cnae_found,
        total_ativas=result.metrics.total_ativas,
        total_consolidated=result.metrics.total_consolidated,
    )

    # ── Proporção de linhas malformadas — mudança parcial de layout que a
    # pré-checagem (só a 1ª linha) não pegaria (item 2) ──
    try:
        check_malformed_ratio(
            "Estabelecimentos (todas as partes)", estab_counts.malformed, estab_counts.total,
            thresholds["max_malformed_row_ratio"],
        )
    except MalformedRowRatioError as exc:
        logger.error("Layout parcialmente mudado — abortando sem escrever em prospect_orgs: %s", exc)
        if not args.dry_run:
            db = SessionLocal()
            try:
                _record_run(
                    db, dump_reference=args.dump_reference, target_cnaes_sorted=target_cnaes_sorted,
                    download_date=download_date, status="aborted_layout_mismatch",
                    started_at=started_at, error_message=str(exc), metrics=metrics,
                    tolerance_params=thresholds, file_count=len(file_hashes),
                    files_sha256=file_hashes, layout_signature=layout_signature,
                )
            finally:
                db.close()
        return 1

    db = SessionLocal()
    try:
        previous = _find_previous_metrics(db, target_cnaes_sorted)

        # ── Guarda de sanidade — DEPOIS de consolidar, ANTES de escrever
        # qualquer linha em prospect_orgs (item 1) ──
        try:
            validate_metrics(metrics, thresholds, previous=previous)
        except SanityCheckError as exc:
            logger.error(
                "Guarda de sanidade disparada — abortando SEM escrever em prospect_orgs: %s", exc
            )
            if not args.dry_run:
                _record_run(
                    db, dump_reference=args.dump_reference, target_cnaes_sorted=target_cnaes_sorted,
                    download_date=download_date, status="aborted_sanity_check",
                    started_at=started_at, error_message=str(exc), metrics=metrics,
                    tolerance_params=thresholds, file_count=len(file_hashes),
                    files_sha256=file_hashes, layout_signature=layout_signature,
                )
            return 1

        if args.dry_run:
            logger.info("--dry-run: nenhuma escrita no banco (nem prospect_orgs, nem prospect_ingestion_runs).")
            return 0

        written = upsert_orgs(db, orgs)
        logger.info("%d registros upsertados em prospect_orgs", written)

        _record_run(
            db, dump_reference=args.dump_reference, target_cnaes_sorted=target_cnaes_sorted,
            download_date=download_date, status="completed",
            started_at=started_at, metrics=metrics, tolerance_params=thresholds,
            file_count=len(file_hashes), files_sha256=file_hashes, layout_signature=layout_signature,
        )
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
