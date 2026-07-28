#!/usr/bin/env python3
"""Parser -> Normalização -> Consolidação -> upsert idempotente em prospect_orgs
(PO-2026-07-SALES-001, Fase 1).

Uso:
  cd backend && source .venv/bin/activate
  python ../tools/prospecting/ingest_cnpj_dump.py \\
      --dump-dir /caminho/para/dump/2026-07 --dump-reference 2026-07

--dump-dir deve conter os arquivos oficiais extraídos (Empresas*, Estabelecimentos*,
Simples*, Socios*, Municipios*), baixados de arquivos.receitafederal.gov.br — ver
README.md deste diretório para o passo a passo completo.
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

from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.prospect_org import ProspectOrg  # noqa: E402
from app.services.prospecting.consolidation import (  # noqa: E402
    TARGET_CNAES,
    ConsolidatedOrg,
    build_consolidated_orgs,
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dump-dir", required=True, type=Path, help="Diretório com os arquivos oficiais extraídos.")
    parser.add_argument("--dump-reference", required=True, help='Ex.: "2026-07" — vintage do dump.')
    parser.add_argument("--target-cnaes", default=",".join(sorted(TARGET_CNAES)))
    parser.add_argument("--dry-run", action="store_true", help="Só parseia e reporta contagens, não escreve no banco.")
    args = parser.parse_args(argv)

    if not args.dump_dir.is_dir():
        parser.error(f"--dump-dir não é um diretório: {args.dump_dir}")

    target_cnaes = frozenset(c.strip() for c in args.target_cnaes.split(",") if c.strip())

    logger.info("Iniciando ingestão: dump_dir=%s dump_reference=%s target_cnaes=%s", args.dump_dir, args.dump_reference, sorted(target_cnaes))
    orgs = build_consolidated_orgs(args.dump_dir, dump_reference=args.dump_reference, target_cnaes=target_cnaes)
    logger.info("%d organizações consolidadas (situação cadastral ativa, dedup por CNPJ básico)", len(orgs))

    if args.dry_run:
        logger.info("--dry-run: nenhuma escrita no banco.")
        return 0

    db = SessionLocal()
    try:
        written = upsert_orgs(db, orgs)
        logger.info("%d registros upsertados em prospect_orgs", written)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
