"""Isolated database: legacy-preserving rollback and committed retention races."""

import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.documents import Document
from app.services.fiscal_foundations import EvidenceLink, preserve_document, record_fact
from tests.test_fiscal_foundations import document, make_world

PREVIOUS = "2026_09_15_0043"
REVISION = "2026_09_17_0044"


@pytest.fixture
def isolated_database(monkeypatch):
    # Alembic env.py calls fileConfig; do not disable application loggers mid-suite.
    monkeypatch.setattr("logging.config.fileConfig", lambda *args, **kwargs: None)
    # Never downgrade the shared test database or application database.
    name = "order07_test_" + uuid4().hex
    admin = create_engine(os.environ["DATABASE_URL"], isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = (
        make_url(os.environ["DATABASE_URL"])
        .set(database=name)
        .render_as_string(hide_password=False)
    )
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    config = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    engine = create_engine(url)
    try:
        yield config, engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_upgrade_backfill_and_downgrade_preserve_legacy_rows(isolated_database):
    config, engine = isolated_database
    command.upgrade(config, PREVIOUS)
    tenant_id, legacy_id = uuid4(), uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants(id,name,slug) VALUES (:id,'legacy',:slug)"),
            {"id": tenant_id, "slug": str(tenant_id)},
        )
        conn.execute(
            text("""INSERT INTO manifestacoes_eleicao_ibs_cbs
            (id,tenant_id,cnpj,tipo_manifestacao,manifestada_em,modalidade,eficacia_inicio,eficacia_fim,fonte,evidencia_ref)
            VALUES (:id,:tid,'12345678000190','OPCAO_REGIME_REGULAR','2026-09-15',
            'SIMPLES_COM_IBS_CBS_NO_REGIME_REGULAR','2027-01-01','2027-06-30','legacy source','legacy reference')"""),
            {"id": legacy_id, "tid": tenant_id},
        )
        before = dict(
            conn.execute(
                text("SELECT * FROM manifestacoes_eleicao_ibs_cbs WHERE id=:id"),
                {"id": legacy_id},
            )
            .mappings()
            .one()
        )
    command.upgrade(config, REVISION)
    with engine.connect() as conn:
        after = dict(
            conn.execute(
                text("SELECT * FROM manifestacoes_eleicao_ibs_cbs WHERE id=:id"),
                {"id": legacy_id},
            )
            .mappings()
            .one()
        )
        assert after.pop("regime") == "SIMPLES_NACIONAL"
        assert after.pop("policy_version") == "SIMPLES_2026_V1"
        assert before == after
        assert conn.scalar(text("SELECT count(*) FROM fiscal_facts")) == 0
    command.downgrade(config, PREVIOUS)
    assert "fiscal_facts" not in inspect(engine).get_table_names()
    with engine.connect() as conn:
        assert (
            dict(
                conn.execute(
                    text("SELECT * FROM manifestacoes_eleicao_ibs_cbs WHERE id=:id"),
                    {"id": legacy_id},
                )
                .mappings()
                .one()
            )
            == before
        )
    command.upgrade(config, REVISION)
    assert "fiscal_facts" in inspect(engine).get_table_names()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO fiscal_parties(tenant_id,party_type,identifier) VALUES (:tid,'PF','12345678901')"
            ),
            {"tid": tenant_id},
        )
    with pytest.raises(DBAPIError, match="preserve fiscal history before downgrade"):
        command.downgrade(config, PREVIOUS)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM fiscal_parties")) == 1
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == REVISION


def test_committed_document_lock_and_retention_fail_closed(isolated_database):
    config, engine = isolated_database
    command.upgrade(config, REVISION)
    with Session(engine) as seed:
        world = make_world(seed)
        doc = document(seed, world, age=400)
        tid, did = UUID(str(world[0].id)), UUID(str(doc.id))
        seed.commit()
    with Session(engine) as writer, Session(engine) as purger:
        # Row is visible to the purger before classification, unlike an uncommitted fixture.
        assert (
            purger.scalar(
                text("SELECT count(*) FROM documents WHERE id=:id"), {"id": did}
            )
            == 1
        )
        preserve_document(
            writer, tenant_id=tid, document_id=did, reason="pending policy"
        )
        assert (
            purger.execute(
                text("SELECT id FROM documents WHERE id=:id FOR UPDATE SKIP LOCKED"),
                {"id": did},
            ).all()
            == []
        )
        writer.commit()
        assert (
            purger.execute(
                text(
                    "SELECT id FROM documents WHERE id=:id AND retention_class='STANDARD' FOR UPDATE SKIP LOCKED"
                ),
                {"id": did},
            ).all()
            == []
        )
    with Session(engine) as session:
        from app.tasks import task_j_retention
        from unittest.mock import patch

        with (
            patch.object(task_j_retention, "SessionLocal", return_value=session),
            patch.object(task_j_retention, "delete_object") as delete,
        ):
            task_j_retention.purge_expired_documents()
        delete.assert_not_called()
    with engine.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM documents WHERE id=:id"), {"id": did}
            )
            == 1
        )


def test_evidence_bundle_is_sealed_at_commit(isolated_database):
    config, engine = isolated_database
    command.upgrade(config, REVISION)
    with Session(engine) as seed:
        world = make_world(seed)
        doc = document(seed, world)
        tid, did, eid = UUID(str(world[0].id)), UUID(str(doc.id)), world[4].id
        first = record_fact(
            seed,
            tenant_id=tid,
            kind="OPTION_REQUESTED",
            election_id=eid,
            source="test",
            source_kind="OFFICIAL_RECORD",
            evidence=[EvidenceLink(did, "OPTION_REQUEST")],
        )
        fid = first.id
        seed.commit()
    with engine.begin() as conn:
        with pytest.raises(DBAPIError, match="atomically"):
            conn.execute(
                text("""INSERT INTO fiscal_fact_evidence(tenant_id,fact_id,document_id,evidence_type,checksum_sha256)
                 VALUES (:tid,:fid,:did,'FISCAL_YEAR',:checksum)"""),
                {"tid": tid, "fid": fid, "did": did, "checksum": "a" * 64},
            )
    with Session(engine) as session:
        assert session.get(Document, did) is not None
