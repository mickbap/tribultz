"""Tests for /api/v1/news — list + auto-publish (token-protected)."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import get_db
from app.main import app

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(name="session")
def session_fixture():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(name="client")
def client_fixture(session):
    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture(name="publish_token")
def publish_token_fixture(monkeypatch):
    token = "test-news-token-" + uuid.uuid4().hex[:12]
    monkeypatch.setattr(settings, "NEWS_PUBLISH_TOKEN", token)
    return token


# ── GET /api/v1/news ─────────────────────────────────────────────────────


def test_list_news_returns_200(client):
    resp = client.get("/api/v1/news")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_news_respects_limit_query_param(client, publish_token):
    # Cria 12 entradas para validar que ?limit=N retorna até N e o default fica em 10
    headers = {"Authorization": f"Bearer {publish_token}"}
    for _ in range(12):
        client.post(
            "/api/v1/news",
            json={
                "title": f"Limit probe {uuid.uuid4().hex[:8]}",
                "description": "probe",
                "category": "Feature",
            },
            headers=headers,
        )

    default_resp = client.get("/api/v1/news")
    assert default_resp.status_code == 200
    assert len(default_resp.json()) <= 10

    custom_resp = client.get("/api/v1/news?limit=12")
    assert custom_resp.status_code == 200
    assert len(custom_resp.json()) == 12


def test_list_news_rejects_limit_out_of_range(client):
    assert client.get("/api/v1/news?limit=0").status_code == 422
    assert client.get("/api/v1/news?limit=51").status_code == 422


# ── POST /api/v1/news ────────────────────────────────────────────────────


def test_post_news_without_token_setting_returns_503(client, monkeypatch):
    """Se o servidor não configurou NEWS_PUBLISH_TOKEN, recusa (fail-closed)."""
    monkeypatch.setattr(settings, "NEWS_PUBLISH_TOKEN", "")
    resp = client.post(
        "/api/v1/news",
        json={"title": "x" * 5, "description": "d" * 5, "category": "Feature"},
        headers={"Authorization": "Bearer anything"},
    )
    assert resp.status_code == 503


def test_post_news_without_authorization_header_returns_401(client, publish_token):
    resp = client.post(
        "/api/v1/news",
        json={"title": "Lançamento X", "description": "Detalhe Y", "category": "Feature"},
    )
    assert resp.status_code == 401


def test_post_news_with_wrong_token_returns_401(client, publish_token):
    resp = client.post(
        "/api/v1/news",
        json={"title": "Lançamento X", "description": "Detalhe Y", "category": "Feature"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401


def test_post_news_with_valid_token_creates_entry(client, publish_token, session):
    title = f"E2E test {uuid.uuid4().hex[:8]}"
    resp = client.post(
        "/api/v1/news",
        json={
            "title": title,
            "description": "Implementação concluída via teste integrado.",
            "category": "Feature",
        },
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["title"] == title
    assert body["category"] == "Feature"
    assert "id" in body and "created_at" in body

    # Persistido?
    session.expire_all()
    row = session.execute(
        text("SELECT title, category FROM news WHERE id = :id"),
        {"id": body["id"]},
    ).fetchone()
    assert row is not None
    assert row.title == title


def test_post_news_idempotent_returns_existing_within_30d(client, publish_token):
    title = f"Dup test {uuid.uuid4().hex[:8]}"
    payload = {"title": title, "description": "primeira", "category": "Fix"}
    headers = {"Authorization": f"Bearer {publish_token}"}

    first = client.post("/api/v1/news", json=payload, headers=headers)
    assert first.status_code == 201
    first_id = first.json()["id"]

    # Segundo POST com mesmo título → retorna o existente
    second = client.post(
        "/api/v1/news",
        json={"title": title, "description": "segunda tentativa", "category": "Feature"},
        headers=headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] == first_id
    # Description original preservada (não atualizou)
    assert second.json()["description"] == "primeira"


def test_post_news_validation_rejects_short_title(client, publish_token):
    resp = client.post(
        "/api/v1/news",
        json={"title": "x", "description": "ok descrição", "category": "Feature"},
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    assert resp.status_code == 422


def test_post_news_validation_rejects_invalid_category(client, publish_token):
    resp = client.post(
        "/api/v1/news",
        json={"title": "Título OK", "description": "ok", "category": "Invalid"},
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    assert resp.status_code == 422


def test_post_news_appears_in_list(client, publish_token):
    title = f"List visibility {uuid.uuid4().hex[:8]}"
    client.post(
        "/api/v1/news",
        json={"title": title, "description": "deve aparecer", "category": "Feature"},
        headers={"Authorization": f"Bearer {publish_token}"},
    )
    resp = client.get("/api/v1/news")
    titles = [item["title"] for item in resp.json()]
    assert title in titles
