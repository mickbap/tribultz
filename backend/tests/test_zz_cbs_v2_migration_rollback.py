"""Executa downgrade/upgrade real da infraestrutura CBS v2."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REVISION = "2026_09_15_0043"
PREVIOUS = "2026_09_09_0042"
TABLES = {
    "cbs_v2_sync_runs",
    "cbs_v2_sync_run_events",
    "cbs_v2_external_observations",
}


def _database_url() -> str | None:
    return os.getenv("DATABASE_URL")


pytestmark = pytest.mark.skipif(
    not _database_url(), reason="sem DATABASE_URL (infra local/CI fornecem)"
)


def _config(url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade_reversiveis():
    url = _database_url()
    assert url is not None
    cfg = _config(url)
    assert TABLES <= _tables(url)
    try:
        command.downgrade(cfg, PREVIOUS)
        assert TABLES.isdisjoint(_tables(url))
        command.upgrade(cfg, REVISION)
        assert TABLES <= _tables(url)
    finally:
        command.upgrade(cfg, "head")
