#!/usr/bin/env python3
"""Supressão -> Pré-score -> Top-N -> arquivo de saída + registro em
prospect_scoring_runs (PO-2026-07-SALES-001, Fase 1).

Uso:
  cd backend && source .venv/bin/activate
  python ../tools/prospecting/score_and_select.py \\
      --rubric-version v1 --dump-reference 2026-07 --top-n 2000

Cada execução real (sem --dry-run) grava uma linha nova em prospect_scoring_runs
(append-only) com a versão/checksum da rubrica usada — isso é o que permite, em
fase futura, reprocessar uma lista antiga com outra rubrica e comparar
estatisticamente os resultados sem qualquer migration nova.
"""

from __future__ import annotations

import argparse
import csv as csv_module
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.prospect_org import ProspectOrg  # noqa: E402
from app.models.prospect_scoring_run import ProspectScoringRun  # noqa: E402
from app.services.prospecting.rubric_loader import load_rubric  # noqa: E402
from app.services.prospecting.scoring import ScoreInput, compute_score  # noqa: E402
from app.services.prospecting.suppression import (  # noqa: E402
    DEFAULT_EXCLUDE_STATUSES,
    filter_candidates,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("prospecting.score_and_select")

CSV_FIELDS = [
    "cnpj_basico", "razao_social", "nome_fantasia", "municipio_nome", "uf",
    "email", "telefone1", "score", "tier", "rubric_version", "justificativa",
]


def _score_input_from_org(org: ProspectOrg) -> ScoreInput:
    return ScoreInput(
        qtd_socios=org.qtd_socios,
        porte=org.porte,
        opcao_mei=org.opcao_mei,
        capital_social=org.capital_social,
        data_inicio_atividade=org.data_inicio_atividade,
        email_domain_category=org.email_domain_category or "ausente",
        qtd_estabelecimentos=org.qtd_estabelecimentos,
        uf=org.uf,
        razao_social=org.razao_social,
    )


def _rows_for_output(scored: list[tuple[ProspectOrg, "object"]]) -> list[dict]:
    return [
        {
            "cnpj_basico": org.cnpj_basico,
            "razao_social": org.razao_social,
            "nome_fantasia": org.nome_fantasia,
            "municipio_nome": org.municipio_nome,
            "uf": org.uf,
            "email": org.email,
            "telefone1": org.telefone1,
            "score": result.score,
            "tier": result.tier,
            "rubric_version": result.rubric_version,
            "justificativa": result.justification,
        }
        for org, result in scored
    ]


def _write_output(rows: list[dict], output_path: Path, fmt: str) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    else:
        with output_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv_module.DictWriter(fh, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    return hashlib.sha256(output_path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rubric-version", help='Ex.: "v1" -> rubric_v1.yaml.')
    parser.add_argument("--rubric-path", help="Override explícito (usado pelos testes).")
    parser.add_argument("--dump-reference", required=True)
    parser.add_argument("--top-n", type=int, default=2000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument(
        "--suppress-statuses",
        default=",".join(sorted(DEFAULT_EXCLUDE_STATUSES)),
        help="opt_out/cliente são sempre aplicados independente desta lista.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Não escreve arquivo nem grava prospect_scoring_runs.")
    args = parser.parse_args(argv)

    if not args.rubric_version and not args.rubric_path:
        parser.error("Informe --rubric-version ou --rubric-path.")

    rubric = load_rubric(version=args.rubric_version, path=args.rubric_path)
    exclude_statuses = frozenset(s.strip() for s in args.suppress_statuses.split(",") if s.strip())

    started_at = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        all_orgs = list(
            db.execute(select(ProspectOrg).where(ProspectOrg.dedup_status != "merged")).scalars().all()
        )
        logger.info("%d organizações elegíveis (dedup_status != 'merged')", len(all_orgs))

        candidates = filter_candidates(db, all_orgs, exclude_statuses=exclude_statuses)
        logger.info("%d após filtro de supressão (excluídos: %s)", len(candidates), sorted(exclude_statuses))

        scored = []
        for org in candidates:
            result = compute_score(_score_input_from_org(org), rubric)
            org.pre_score = result.score
            org.pre_score_tier = result.tier
            org.pre_score_rubric_version = result.rubric_version
            org.pre_scored_at = started_at
            scored.append((org, result))

        scored.sort(key=lambda pair: pair[1].score, reverse=True)
        top = scored[: args.top_n]
        rows = _rows_for_output(top)

        if args.dry_run:
            logger.info(
                "--dry-run: %d candidatos pontuados, %d selecionados para o Top-N — nenhuma escrita.",
                len(candidates), len(top),
            )
            db.rollback()
            return 0

        output_path = args.output or (
            _REPO_ROOT / "reports" / "prospecting" / f"top_candidates_{rubric.version}_{args.dump_reference}.{args.format}"
        )
        output_checksum = _write_output(rows, output_path, args.format)

        run = ProspectScoringRun(
            rubric_version=rubric.version,
            rubric_checksum=rubric.checksum,
            source_dump_reference=args.dump_reference,
            params={
                "top_n": args.top_n,
                "suppress_statuses": sorted(exclude_statuses),
                "output": str(output_path),
                "format": args.format,
            },
            candidate_count=len(candidates),
            selected_count=len(top),
            output_uri=str(output_path),
            output_checksum=output_checksum,
            status="completed",
            run_started_at=started_at,
            run_finished_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        logger.info("Top %d escrito em %s (run_id=%s, rubrica=%s)", len(top), output_path, run.id, rubric.version)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
