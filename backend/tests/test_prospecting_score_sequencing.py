"""Trava de sequenciamento de score_and_select.py (Ordem Complementar, item 4) — DB-backed.

check_sequencing() bloqueia a pontuação sem exceção quando não há ingestão
concluída, ou quando a deduplicação concluída mais recente é anterior à
ingestão concluída mais recente — "não será permitido utilizar dados
parcialmente processados". Sem flag de bypass.
"""

from __future__ import annotations

import importlib
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_PROSPECTING = _REPO_ROOT / "tools" / "prospecting"
if str(_TOOLS_PROSPECTING) not in sys.path:
    sys.path.insert(0, str(_TOOLS_PROSPECTING))

score_and_select = importlib.import_module("score_and_select")

from app.models.prospect_dedup_run import ProspectDedupRun  # noqa: E402
from app.models.prospect_ingestion_run import ProspectIngestionRun  # noqa: E402

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture()
def session():
    """check_sequencing() consulta a execução mais recente por tabela inteira
    (sem escopo por dump_reference) — precisamos de uma tabela limpa para que
    as asserções sejam determinísticas, independente de outras suítes terem
    deixado ProspectIngestionRun/ProspectDedupRun reais para trás. Limpeza é
    um DELETE real e comprometido, porque essas linhas residuais vêm de
    sessões próprias (SessionLocal real) de outros testes, não desta
    transação — um rollback nosso não as desfaria."""
    cleanup = TestingSessionLocal()
    try:
        cleanup.execute(delete(ProspectDedupRun))
        cleanup.execute(delete(ProspectIngestionRun))
        cleanup.commit()
    finally:
        cleanup.close()

    connection = engine.connect()
    transaction = connection.begin()
    db = TestingSessionLocal(bind=connection)
    yield db
    db.close()
    transaction.rollback()
    connection.close()


def _make_ingestion_run(session, *, finished_at, status="completed") -> ProspectIngestionRun:
    run = ProspectIngestionRun(
        dump_reference=f"seq-{uuid.uuid4().hex[:8]}",
        target_cnaes=["6920601"],
        download_date=finished_at.date(),
        status=status,
        started_at=finished_at - timedelta(minutes=5),
        finished_at=finished_at if status == "completed" else None,
    )
    session.add(run)
    session.flush()
    return run


def _make_dedup_run(session, *, finished_at, status="completed") -> ProspectDedupRun:
    run = ProspectDedupRun(
        status=status,
        started_at=finished_at - timedelta(minutes=5),
        finished_at=finished_at if status == "completed" else None,
    )
    session.add(run)
    session.flush()
    return run


class TestCheckSequencing:
    def test_blocks_when_no_ingestion_exists(self, session):
        with pytest.raises(score_and_select.SequencingError, match="ingest_cnpj_dump"):
            score_and_select.check_sequencing(session)

    def test_blocks_when_no_dedup_exists(self, session):
        _make_ingestion_run(session, finished_at=datetime.now(timezone.utc))
        with pytest.raises(score_and_select.SequencingError, match="dedup_prospects"):
            score_and_select.check_sequencing(session)

    def test_blocks_when_dedup_is_older_than_ingestion(self, session):
        now = datetime.now(timezone.utc)
        _make_dedup_run(session, finished_at=now - timedelta(hours=1))
        _make_ingestion_run(session, finished_at=now)
        with pytest.raises(score_and_select.SequencingError, match="dedup_prospects"):
            score_and_select.check_sequencing(session)

    def test_ignores_failed_ingestion_run(self, session):
        now = datetime.now(timezone.utc)
        _make_ingestion_run(session, finished_at=now, status="failed")
        _make_dedup_run(session, finished_at=now)
        with pytest.raises(score_and_select.SequencingError, match="ingest_cnpj_dump"):
            score_and_select.check_sequencing(session)

    def test_ignores_failed_dedup_run(self, session):
        now = datetime.now(timezone.utc)
        _make_ingestion_run(session, finished_at=now - timedelta(hours=1))
        _make_dedup_run(session, finished_at=now, status="failed")
        with pytest.raises(score_and_select.SequencingError, match="dedup_prospects"):
            score_and_select.check_sequencing(session)

    def test_passes_when_dedup_follows_ingestion(self, session):
        now = datetime.now(timezone.utc)
        _make_ingestion_run(session, finished_at=now - timedelta(hours=1))
        _make_dedup_run(session, finished_at=now)
        score_and_select.check_sequencing(session)  # não deve levantar

    def test_passes_when_dedup_and_ingestion_finish_at_same_instant(self, session):
        now = datetime.now(timezone.utc)
        _make_ingestion_run(session, finished_at=now)
        _make_dedup_run(session, finished_at=now)
        score_and_select.check_sequencing(session)  # >= é aceito, não só >
