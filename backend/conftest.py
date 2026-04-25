"""Root conftest — prepares env + optional Postgres testcontainer.

pytest_configure runs before collection, so Settings() never sees a missing
variable and tests that create engines at import time see a reachable DB.

Postgres strategy:
  - CI (env var CI=true) or USE_EXTERNAL_DB=1: respect existing DATABASE_URL
  - Otherwise: spin up a fresh Postgres 16 container via testcontainers and
    run alembic upgrade head against it. Container is torn down at session end.

All non-DB values are deterministic test doubles — never connect to real infra.
"""

from __future__ import annotations

import os
from pathlib import Path


_postgres_container = None


def _use_external_db() -> bool:
    return os.getenv("USE_EXTERNAL_DB") == "1" or os.getenv("CI") == "true"


def _run_alembic_upgrade(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(Path(__file__).parent / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")


def _start_postgres_container() -> str | None:
    """Start a Postgres testcontainer and return the connection URL.

    Returns None if testcontainers is not installed or Docker is unavailable —
    callers then fall back to whatever DATABASE_URL is already in env.
    """
    global _postgres_container

    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        return None

    try:
        _postgres_container = PostgresContainer(
            "postgres:16-alpine",
            username="tribultz",
            password="tribultz",
            dbname="tribultz",
        )
        _postgres_container.start()
    except Exception:
        _postgres_container = None
        return None

    return _postgres_container.get_connection_url()


def pytest_configure(config):  # noqa: ARG001
    global _postgres_container

    defaults = {
        "POSTGRES_PASSWORD": "test-password",
        "DATABASE_URL": "postgresql+psycopg2://tribultz:test-password@localhost:5432/tribultz_test",
        "REDIS_URL": "redis://localhost:6379/15",
        "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
        "MINIO_ROOT_USER": "test-minio-user",
        "MINIO_ROOT_PASSWORD": "test-minio-password",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_BUCKET": "tribultz-test",
        "S3_ACCESS_KEY": "test-minio-user",
        "S3_SECRET_KEY": "test-minio-password",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)

    if not _use_external_db():
        url = _start_postgres_container()
        if url is not None:
            os.environ["DATABASE_URL"] = url
            try:
                _run_alembic_upgrade(url)
            except Exception:
                if _postgres_container is not None:
                    _postgres_container.stop()
                    _postgres_container = None
                raise


def pytest_unconfigure(config):  # noqa: ARG001
    global _postgres_container
    if _postgres_container is not None:
        _postgres_container.stop()
        _postgres_container = None
