"""Rollback REAL da migration que dropa a tabela vestigial `messages` (#412).

Mesmo padrão de tests/test_zz_handoff_migration_rollback.py: não basta
verificar que existe função downgrade() — a reversão é executada de fato.
Desce a revisão, confere que `messages` volta a existir, sobe de novo,
confere que some outra vez, e restaura head SEMPRE (a suíte depende disso).

Prefixo zz_ no nome: roda por último na ordenação de arquivos — churn de
schema no meio da suíte é convite a flake.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REVISION = "2026_09_09_0042"
PREVIOUS = "2026_09_07_0041"
TABLE = "messages"


def _database_url() -> str | None:
    return os.getenv("DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not _database_url(), reason="sem DATABASE_URL (infra local/CI fornecem)"
)


def _alembic_config(url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade_reversiveis():
    url = _database_url()
    assert url is not None
    cfg = _alembic_config(url)

    assert TABLE not in _table_names(url), "estado inicial (head) já dropou messages"

    try:
        command.downgrade(cfg, PREVIOUS)
        assert TABLE in _table_names(url), "downgrade deveria recriar messages"

        command.upgrade(cfg, REVISION)
        assert TABLE not in _table_names(url), "upgrade deveria dropar messages de novo"
    finally:
        # Nunca deixar a base fora de head — quem vier depois depende disso.
        command.upgrade(cfg, "head")
