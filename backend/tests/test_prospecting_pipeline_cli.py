"""Teste fim-a-fim dos 3 scripts CLI da Fase 1 (PO-2026-07-SALES-001) — Postgres real.

Chama main() de cada script diretamente (não via subprocess, para velocidade e
cobertura), contra as mesmas fixtures usadas pelos testes de parser/consolidação.

Cada execução usa um --dump-reference único (uuid) para poder limpar depois só
os registros deste teste — score_and_select.py e dedup_prospects.py operam
sobre TODA a tabela prospect_orgs por design (é o "estado atual do mundo" a
pontuar/deduplicar, não um recorte por dump), então a limpeza no teardown é o
que evita que uma execução deste teste contamine as demais.

Os testes usam --sanity-thresholds-path com limites permissivos: o fixture só
tem ~4 organizações, bem abaixo do min_target_cnae_found padrão (pensado para
o dump real, ~80 mil) — sem isso, todo ingest de teste seria abortado pela
própria guarda de sanidade que estamos testando.
"""

from __future__ import annotations

import csv
import importlib
import json
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

from app.models.prospect_ingestion_run import ProspectIngestionRun  # noqa: E402
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
        session.execute(
            delete(ProspectIngestionRun).where(ProspectIngestionRun.dump_reference == ref)
        )
        session.execute(delete(ProspectOrg).where(ProspectOrg.source_dump_reference == ref))
        session.commit()
    finally:
        session.close()


def _write_thresholds(path: Path, **overrides) -> Path:
    defaults = dict(
        min_target_cnae_found=0,
        max_target_cnae_found=1_000_000,
        min_ativas_ratio=0.0,
        max_relative_change_vs_last_run=100.0,
        max_malformed_row_ratio=1.0,
    )
    defaults.update(overrides)
    lines = "\n".join(f"{k}: {v}" for k, v in defaults.items())
    path.write_text(lines + "\n")
    return path


@pytest.fixture()
def lenient_thresholds_path(tmp_path) -> Path:
    """Limites permissivos — o fixture tem só ~4 organizações."""
    return _write_thresholds(tmp_path / "lenient_thresholds.yaml")


def _ingest_args(dump_reference: str, thresholds_path: Path, *extra: str) -> list[str]:
    return [
        "--dump-dir", str(FIXTURE_DIR),
        "--dump-reference", dump_reference,
        "--download-date", "2026-07-01",
        "--sanity-thresholds-path", str(thresholds_path),
        *extra,
    ]


class TestFullPipeline:
    def test_ingest_is_idempotent(self, dump_reference, lenient_thresholds_path):
        rc1 = ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))
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
        rc2 = ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))
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

    def test_ingest_dry_run_writes_nothing(self, dump_reference, lenient_thresholds_path):
        rc = ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path, "--dry-run"))
        assert rc == 0
        session = TestingSessionLocal()
        try:
            org_count = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .count()
            )
            run_count = (
                session.query(ProspectIngestionRun)
                .filter(ProspectIngestionRun.dump_reference == dump_reference)
                .count()
            )
            assert org_count == 0
            assert run_count == 0
        finally:
            session.close()

    def test_full_pipeline_ingest_dedup_score(self, dump_reference, lenient_thresholds_path, tmp_path):
        rc_ingest = ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))
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

    def test_score_and_select_dry_run_writes_no_run_row(self, dump_reference, lenient_thresholds_path, tmp_path):
        ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))

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

    def test_json_output_format(self, dump_reference, lenient_thresholds_path, tmp_path):
        ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))
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
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert any(row["cnpj_basico"] in EXPECTED_CNPJS for row in data)


class TestIngestionSafeguards:
    """Ordem Complementar — guarda de sanidade (item 1), validação de layout
    (item 2) e o rastro de auditoria que cada execução real deixa (item 8)."""

    def test_records_completed_run_with_metrics(self, dump_reference, lenient_thresholds_path):
        rc = ingest_cnpj_dump.main(_ingest_args(dump_reference, lenient_thresholds_path))
        assert rc == 0

        session = TestingSessionLocal()
        try:
            run = (
                session.query(ProspectIngestionRun)
                .filter(ProspectIngestionRun.dump_reference == dump_reference)
                .one()
            )
            assert cast(str, run.status) == "completed"
            assert cast(int, run.total_target_cnae_found) == 4  # ALPHA, BETA, GAMA, DELTA
            assert cast(int, run.total_ativas) == 3  # GAMA excluída (baixada)
            assert cast(int, run.total_consolidated) == 3
            assert cast(int, run.total_estabelecimentos_scanned) == 7
            assert cast(str, run.layout_signature)
            assert cast(dict, run.files_sha256)  # hash de proveniência gravado
            assert run.download_date is not None
        finally:
            session.close()

    def test_missing_download_date_is_rejected(self, dump_reference, lenient_thresholds_path):
        with pytest.raises(SystemExit):
            ingest_cnpj_dump.main(
                [
                    "--dump-dir", str(FIXTURE_DIR),
                    "--dump-reference", dump_reference,
                    "--sanity-thresholds-path", str(lenient_thresholds_path),
                ]
            )

    def test_invalid_download_date_is_rejected(self, dump_reference, lenient_thresholds_path):
        with pytest.raises(SystemExit):
            ingest_cnpj_dump.main(
                [
                    "--dump-dir", str(FIXTURE_DIR),
                    "--dump-reference", dump_reference,
                    "--download-date", "não-é-uma-data",
                    "--sanity-thresholds-path", str(lenient_thresholds_path),
                ]
            )

    def test_layout_mismatch_aborts_before_any_write(self, dump_reference, tmp_path, lenient_thresholds_path):
        # Diretório sem nenhum arquivo da RF — detect_layout_signature deve
        # abortar antes de qualquer parsing.
        empty_dir = tmp_path / "dump_vazio"
        empty_dir.mkdir()

        rc = ingest_cnpj_dump.main(
            [
                "--dump-dir", str(empty_dir),
                "--dump-reference", dump_reference,
                "--download-date", "2026-07-01",
                "--sanity-thresholds-path", str(lenient_thresholds_path),
            ]
        )
        assert rc == 1

        session = TestingSessionLocal()
        try:
            org_count = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .count()
            )
            run = (
                session.query(ProspectIngestionRun)
                .filter(ProspectIngestionRun.dump_reference == dump_reference)
                .one()
            )
            assert org_count == 0  # nada foi escrito em prospect_orgs
            assert cast(str, run.status) == "aborted_layout_mismatch"
            assert cast(str, run.error_message)
        finally:
            session.close()

    def test_sanity_check_aborts_without_writing_orgs(self, dump_reference, tmp_path):
        # Threshold estrito o suficiente para rejeitar o fixture (4 encontrados).
        strict_path = _write_thresholds(tmp_path / "strict.yaml", min_target_cnae_found=1000)

        rc = ingest_cnpj_dump.main(
            [
                "--dump-dir", str(FIXTURE_DIR),
                "--dump-reference", dump_reference,
                "--download-date", "2026-07-01",
                "--sanity-thresholds-path", str(strict_path),
            ]
        )
        assert rc == 1

        session = TestingSessionLocal()
        try:
            org_count = (
                session.query(ProspectOrg)
                .filter(ProspectOrg.source_dump_reference == dump_reference)
                .count()
            )
            run = (
                session.query(ProspectIngestionRun)
                .filter(ProspectIngestionRun.dump_reference == dump_reference)
                .one()
            )
            assert org_count == 0  # guarda de sanidade impede qualquer escrita em prospect_orgs
            assert cast(str, run.status) == "aborted_sanity_check"
            assert cast(str, run.error_message)
            assert cast(int, run.total_target_cnae_found) == 4  # métricas ficam registradas mesmo abortando
        finally:
            session.close()

    def test_find_previous_metrics_scoped_by_target_cnaes(self, dump_reference):
        """Uma execução concluída com --target-cnaes diferente nunca deve ser
        usada como baseline de variação relativa (item 1) — configs diferentes
        não são comparáveis entre si."""
        session = TestingSessionLocal()
        try:
            from datetime import date, datetime, timezone

            now = datetime.now(timezone.utc)
            session.add(
                ProspectIngestionRun(
                    dump_reference=dump_reference,
                    target_cnaes=["1111111"],  # config DIFERENTE
                    download_date=date(2026, 7, 1),
                    status="completed",
                    total_target_cnae_found=999_999,  # se isso vazar como baseline, o teste falha
                    total_ativas=999_999,
                    total_consolidated=999_999,
                    total_estabelecimentos_scanned=999_999,
                    started_at=now,
                    finished_at=now,
                )
            )
            session.add(
                ProspectIngestionRun(
                    dump_reference=dump_reference,
                    target_cnaes=["6920601", "6920602"],  # config IGUAL à consultada
                    download_date=date(2026, 7, 1),
                    status="completed",
                    total_target_cnae_found=4,
                    total_ativas=3,
                    total_consolidated=3,
                    total_estabelecimentos_scanned=7,
                    started_at=now,
                    finished_at=now,
                )
            )
            session.commit()

            previous = ingest_cnpj_dump._find_previous_metrics(session, ["6920601", "6920602"])
            assert previous is not None
            assert previous.total_target_cnae_found == 4  # não o 999_999 do outro target_cnaes
        finally:
            session.close()
