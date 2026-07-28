#!/usr/bin/env python3
"""Passada de dedup por domínio de e-mail nominal (PO-2026-07-SALES-001, Fase 1).

Só banco de dados — não toca nos arquivos da RF. Idempotente: reseta e
recalcula os grupos do zero a cada execução, então é seguro rodar de novo a
qualquer momento (ex.: depois de um novo ingest).

Uso:
  cd backend && source .venv/bin/activate
  python ../tools/prospecting/dedup_prospects.py [--max-group-size 5]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BACKEND_ROOT = _REPO_ROOT / "backend"
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.database import SessionLocal  # noqa: E402
from app.services.prospecting.dedup import DEFAULT_MAX_GROUP_SIZE, apply_dedup  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("prospecting.dedup_prospects")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--max-group-size", type=int, default=DEFAULT_MAX_GROUP_SIZE,
        help="Domínio compartilhado por mais organizações que isso não é mesclado "
             "(mais provável ser plataforma white-label do que uma única firma).",
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        summary = apply_dedup(db, max_group_size=args.max_group_size)
    finally:
        db.close()

    logger.info(
        "Dedup concluído: %d grupos mesclados, %d organizações marcadas 'merged', "
        "%d domínios pulados (grupo maior que --max-group-size=%d)",
        summary.groups_merged, summary.orgs_merged,
        summary.domains_skipped_too_large, args.max_group_size,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
