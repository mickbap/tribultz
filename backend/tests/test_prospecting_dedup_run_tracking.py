"""Rastreamento de execução de dedup_prospects.py (Ordem Complementar, item 4) —
Postgres real. Cobre a gravação de ProspectDedupRun a cada execução, que é o
que permite a score_and_select.py verificar sequenciamento sem depender de
ordem manual de scripts."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_PROSPECTING = _REPO_ROOT / "tools" / "prospecting"
if str(_TOOLS_PROSPECTING) not in sys.path:
    sys.path.insert(0, str(_TOOLS_PROSPECTING))

dedup_prospects = importlib.import_module("dedup_prospects")

from app.models.prospect_dedup_run import ProspectDedupRun  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def cleanup_dedup_runs():
    """dedup_prospects.py usa SessionLocal() próprio e commita de verdade —
    sem rollback de transação de teste, então a limpeza no teardown é
    obrigatória (mesmo padrão de test_prospecting_pipeline_cli.py)."""
    session = TestingSessionLocal()
    try:
        before_ids = set(session.execute(select(ProspectDedupRun.id)).scalars().all())
    finally:
        session.close()

    yield

    session = TestingSessionLocal()
    try:
        after = session.execute(select(ProspectDedupRun)).scalars().all()
        for run in after:
            if run.id not in before_ids:
                session.delete(run)
        session.commit()
    finally:
        session.close()


class TestDedupRunTracking:
    def test_records_completed_run_with_metrics(self, cleanup_dedup_runs):
        rc = dedup_prospects.main([])
        assert rc == 0

        session = TestingSessionLocal()
        try:
            latest = (
                session.query(ProspectDedupRun)
                .order_by(ProspectDedupRun.created_at.desc())
                .first()
            )
            assert latest is not None
            assert latest.status == "completed"
            assert latest.groups_merged is not None
            assert latest.orgs_merged is not None
            assert latest.domains_skipped_too_large is not None
            assert latest.started_at is not None
            assert latest.finished_at is not None
            assert latest.finished_at >= latest.started_at
        finally:
            session.close()

    def test_respects_max_group_size_argument(self, cleanup_dedup_runs):
        rc = dedup_prospects.main(["--max-group-size", "3"])
        assert rc == 0

        session = TestingSessionLocal()
        try:
            latest = (
                session.query(ProspectDedupRun)
                .order_by(ProspectDedupRun.created_at.desc())
                .first()
            )
            assert latest is not None
            assert latest.status == "completed"
        finally:
            session.close()
