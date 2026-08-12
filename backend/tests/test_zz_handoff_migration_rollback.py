"""Rollback REAL da migration do handoff — Round 8 §2.3 (DEC-9).

Portado (comportamento, não duplicação) da linha descartada
feat/commercial-handoff-f1-f3 (tip 37557a9), adaptado às tabelas canônicas.
"Não basta verificar que existe função downgrade() — quero a reversão
executada": desce a revisão, confere que as quatro tabelas somem, sobe de
novo, confere que voltam, e restaura head SEMPRE (a suíte depende disso).

Prefixo zz_ no nome: roda por último na ordenação de arquivos — churn de
schema no meio da suíte é convite a flake.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

REVISION = "2026_08_12_0037"
PREVIOUS = "2026_07_28_0036"
TABLES = (
    "crm_person_identities",
    "crm_lead_links",
    "crm_lead_events",
    "crm_state_transitions",
)


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

    assert set(TABLES) <= _table_names(url), "estado inicial deveria estar em head"

    try:
        command.downgrade(cfg, PREVIOUS)
        restantes = _table_names(url) & set(TABLES)
        assert restantes == set(), f"downgrade deixou artefatos para trás: {restantes}"

        command.upgrade(cfg, REVISION)
        pos = _table_names(url)
        assert set(TABLES) <= pos, "upgrade não recriou as tabelas"
    finally:
        # Nunca deixar a base fora de head — quem vier depois depende disso.
        command.upgrade(cfg, "head")

    # constraints que carregam garantias voltaram junto
    engine = create_engine(url)
    try:
        insp = inspect(engine)
        uniques = {u["name"] for u in insp.get_unique_constraints("crm_lead_events")}
        assert "uq_crm_lead_events_idempotency" in uniques
        uniques_links = {u["name"] for u in insp.get_unique_constraints("crm_lead_links")}
        assert "uq_crm_lead_links_identity" in uniques_links
    finally:
        engine.dispose()
