"""Root conftest — injects minimal env vars before any app module is imported.

pytest_configure runs before collection, so Settings() never sees a missing variable.
All values are deterministic test doubles — never connect to real infrastructure.
"""

import os


def pytest_configure(config):  # noqa: ARG001
    defaults = {
        # Postgres
        "POSTGRES_PASSWORD": "test-password",
        "DATABASE_URL": "postgresql+psycopg2://tribultz:test-password@localhost:5432/tribultz_test",
        # Redis
        "REDIS_URL": "redis://localhost:6379/15",
        # JWT
        "JWT_SECRET": "test-jwt-secret-minimum-32-characters-long",
        # MinIO / S3
        "MINIO_ROOT_USER": "test-minio-user",
        "MINIO_ROOT_PASSWORD": "test-minio-password",
        "S3_ENDPOINT": "http://localhost:9000",
        "S3_BUCKET": "tribultz-test",
        "S3_ACCESS_KEY": "test-minio-user",
        "S3_SECRET_KEY": "test-minio-password",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
