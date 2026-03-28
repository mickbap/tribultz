from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from crewai import Memory

from app.crews.memory_system import RedisMemoryStorage, ScopedCrewMemory


def _embedder(texts: list[str]) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for text in texts:
        normalized = text.lower()
        if "84713012" in normalized:
            embeddings.append([1.0, 0.0, 0.0])
        elif "2104900" in normalized:
            embeddings.append([0.0, 1.0, 0.0])
        else:
            embeddings.append([0.0, 0.0, 1.0])
    return embeddings


def _memory(namespace: str, ttl_seconds: int = 600) -> Memory:
    storage = RedisMemoryStorage(namespace=namespace, ttl_seconds=ttl_seconds)
    storage.reset()
    return Memory(
        llm=object(),
        storage=storage,
        embedder=_embedder,
    )


def _scoped_memory(memory: Memory, tenant_id: str) -> ScopedCrewMemory:
    base = f"/tenants/{tenant_id}"
    return ScopedCrewMemory(
        memory=memory,
        recall_scopes=[
            f"{base}/transactions/test-run",
            f"{base}/long_term/fiscal_classification",
            f"{base}/entities/fiscal_classification",
        ],
        write_scope=f"{base}/long_term/fiscal_classification",
        default_categories=["precedent", "fiscal_classification"],
        default_metadata={"tenant_id": tenant_id},
        source=tenant_id,
    )


def test_memory_is_isolated_per_tenant_in_redis() -> None:
    namespace = f"tribultz:test:memory:{uuid4()}"
    memory = _memory(namespace)
    tenant_1_memory = _scoped_memory(memory, "tenant_1")
    tenant_2_memory = _scoped_memory(memory, "tenant_2")

    shared_precedent = (
        "Precedente fiscal: NCM 84713012, CST 000 e cClassTrib 654321 "
        "devem manter validacao PASS."
    )

    tenant_1_memory.remember(
        shared_precedent,
        metadata={
            "tenant_id": "tenant_1",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
        importance=0.9,
    )
    tenant_2_memory.remember(
        shared_precedent,
        metadata={
            "tenant_id": "tenant_2",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
        importance=0.9,
    )
    tenant_1_memory.drain_writes()
    tenant_2_memory.drain_writes()

    tenant_1_matches = tenant_1_memory.recall(
        "Buscar precedente fiscal para NCM 84713012",
        depth="shallow",
        limit=5,
    )
    tenant_2_matches = tenant_2_memory.recall(
        "Buscar precedente fiscal para NCM 84713012",
        depth="shallow",
        limit=5,
    )

    assert len(tenant_1_matches) == 1
    assert len(tenant_2_matches) == 1
    assert tenant_1_matches[0].record.metadata["tenant_id"] == "tenant_1"
    assert tenant_2_matches[0].record.metadata["tenant_id"] == "tenant_2"
    assert tenant_1_matches[0].record.id != tenant_2_matches[0].record.id

    storage = RedisMemoryStorage(namespace=namespace, ttl_seconds=600)
    storage.reset()


def test_memory_records_receive_ttl() -> None:
    namespace = f"tribultz:test:memory:{uuid4()}"
    ttl_seconds = 120
    memory = _memory(namespace, ttl_seconds=ttl_seconds)
    tenant_memory = _scoped_memory(memory, "tenant_ttl")

    record = tenant_memory.remember(
        "Memoria com expiracao para NCM 84713012 e CST 000.",
        metadata={"tenant_id": "tenant_ttl"},
        importance=0.8,
    )
    tenant_memory.drain_writes()

    assert record is not None
    storage = RedisMemoryStorage(namespace=namespace, ttl_seconds=ttl_seconds)
    ttl = storage.get_record_ttl_seconds(record.id)
    assert ttl > 0
    assert ttl <= ttl_seconds
    storage.reset()
