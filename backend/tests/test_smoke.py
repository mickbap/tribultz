"""Minimal smoke tests for CI gate."""

import os

# Set required env vars before importing app (database.py reads DATABASE_URL on import)
os.environ.setdefault("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT_URL", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("S3_SECRET_KEY", "minioadmin")

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_ok():
    r = client.get("/")
    assert r.status_code == 200
    assert "status" in r.json()


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
