"""Conftest for crews tests — replaces real Redis with fakeredis server."""

import fakeredis
import pytest


@pytest.fixture(autouse=True)
def fake_redis_server(monkeypatch):
    """Patch redis.Redis.from_url to return an in-process fakeredis client."""
    server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeRedis(server=server, decode_responses=True)

    monkeypatch.setattr(
        "app.crews.memory_system.Redis.from_url",
        lambda *args, **kwargs: fake_client,
    )
    yield fake_client
