"""Teste fim-a-fim dos 3 scripts CLI da Fase 1 (PO-2026-07-SALES-001) — Postgres real.

Chama main() de cada script diretamente (não via subprocess, para velocidade e
cobertura), contra as mesmas fixtures usadas pelos testes de parser/consolidação.

Cada execução usa um --dump-reference único (uuid) para poder limpar depois só
os registros deste teste — score_and_select.py e dedup_prospects.py operam
sobre TODA a tabela prospect_orgs por design (é o "estado atual do mundo" a
pontuar/deduplicar, não um recorte por dump), então a limpeza no teardown é o
que evita que uma execução deste teste contamine as demais.
"""

from __future__ import annotations

import csv
import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TOOLS_PROSPECTING = _REPO_ROOT / "tools" / "prospecting"
if str(_TOOLS_PROSPECTING) not in sys.path:
    sys.path.insert(0, str(_TOOLS_PROSPECTING))

ingest_cnpj_dump = importlib.import_module("ingest_cnpj_dump")
dedup_prospects = importlib.import_module("dedup_prospects")
score_and_select = importlib.import_module("score_and_select")

from app.models.prospect_org import ProspectOrg  # noqa: E402
from app.models.prospect_scoring_run import ProspectScoringRun  # noqa: E402

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "prospecting"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

EXPECTED_CNPJS = {"10000000", "20000000", "40000000"}  # ALPHA, BETA, DELTA — GAMA excluída, LOJA fora do alvo


@pytest.fixture()
def dump_reference():
    """CLI scripts usam SessionLocal() próprio e commitam de verdade — não há
    rollback de transação de teste aqui (ao contrário dos outros testes
    DB-backed de prospecting). Por isso a limpeza no teardown é obrigatória."""
    ref = f"e2e-{uuid.uuid4().hex[:8]}"
    yield ref
    session = TestingSessionLocal()
    try:
        session.execute(
            delete(ProspectScoringRun).where(ProspectScoringRun.source_dump_reference == ref)
        )
        session.execute(delete(ProspectOrg).where(ProspectOrg.source_dump_reference == ref))
        session.commit()
    finally:
        session.close()


class TestFullPipeline:
    def test_ingest_is_idempotent(self, dump_reference):
        rc1 = ingest_cnpj_dump.main(
            ["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference]
        )
        assert rc1 == 0

        session = TestingSessionLocal()
        try:
            orgs = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .all()
            )
            assert {o.cnpj_basico for o in orgs} == EXPECTED_CNPJS
        finally:
            session.close()

        # reexecutar não duplica (ON CONFLICT DO UPDATE)
        rc2 = ingest_cnpj_dump.main(
            ["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference]
        )
        assert rc2 == 0
        session = TestingSessionLocal()
        try:
            count = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .count()
            )
            assert count == 3
        finally:
            session.close()

    def test_ingest_dry_run_writes_nothing(self, dump_reference):
        rc = ingest_cnpj_dump.main(
            ["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference, "--dry-run"]
        )
        assert rc == 0
        session = TestingSessionLocal()
        try:
            count = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .count()
            )
            assert count == 0
        finally:
            session.close()

    def test_full_pipeline_ingest_dedup_score(self, dump_reference, tmp_path):
        rc_ingest = ingest_cnpj_dump.main(
            ["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference]
        )
        assert rc_ingest == 0

        rc_dedup = dedup_prospects.main([])
        assert rc_dedup == 0

        output_path = tmp_path / "top.csv"
        rc_score = score_and_select.main(
            [
                "--rubric-version", "v1",
                "--dump-reference", dump_reference,
                "--output", str(output_path),
                "--format", "csv",
                "--top-n", "2000",
            ]
        )
        assert rc_score == 0
        assert output_path.exists()

        with output_path.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        my_rows = {r["cnpj_basico"]: r for r in rows if r["cnpj_basico"] in EXPECTED_CNPJS}
        assert set(my_rows) == EXPECTED_CNPJS
        for row in my_rows.values():
            assert row["rubric_version"] == "v1"
            assert row["tier"] in ("A", "B", "C", "D")
            assert row["justificativa"]

        session = TestingSessionLocal()
        try:
            run = (
                session.query(ProspectScoringRun)
                .filter(ProspectScoringRun.source_dump_reference == dump_reference)
                .one()
            )
            assert cast(str, run.rubric_version) == "v1"
            assert cast(int, run.candidate_count) >= 3
            assert cast(int, run.selected_count) >= 3
            assert cast(str, run.output_uri) == str(output_path)
        finally:
            session.close()

    def test_score_and_select_dry_run_writes_no_run_row(self, dump_reference, tmp_path):
        ingest_cnpj_dump.main(["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference])

        output_path = tmp_path / "would_not_be_written.csv"
        rc = score_and_select.main(
            [
                "--rubric-version", "v1",
                "--dump-reference", dump_reference,
                "--output", str(output_path),
                "--dry-run",
            ]
        )
        assert rc == 0
        assert not output_path.exists()

        session = TestingSessionLocal()
        try:
            count = (
                session.query(ProspectScoringRun)
                .filter(ProspectScoringRun.source_dump_reference == dump_reference)
                .count()
            )
            assert count == 0
        finally:
            session.close()

    def test_json_output_format(self, dump_reference, tmp_path):
        ingest_cnpj_dump.main(["--dump-dir", str(FIXTURE_DIR), "--dump-reference", dump_reference])
        output_path = tmp_path / "top.json"
        rc = score_and_select.main(
            [
                "--rubric-version", "v1",
                "--dump-reference", dump_reference,
                "--output", str(output_path),
                "--format", "json",
            ]
        )
        assert rc == 0
        import json
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert any(row["cnpj_basico"] in EXPECTED_CNPJS for row in data)
