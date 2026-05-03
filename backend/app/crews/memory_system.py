from __future__ import annotations

import json
import logging
import math
from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock
from typing import Any, cast

import httpx
from crewai.memory.storage.backend import StorageBackend
from crewai.memory.types import MemoryMatch, MemoryRecord, ScopeInfo, compute_composite_score
from redis import Redis

from app.config import settings

logger = logging.getLogger(__name__)


def _normalize_scope(scope: str | None) -> str:
    value = (scope or "/").rstrip("/") or "/"
    return value if value.startswith("/") else f"/{value}"


def _datetime_from_iso(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


class OpenAICompatibleEmbedder:
    """Small OpenAI-compatible embedder client, usable with OpenRouter or OpenAI."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str = "openai/text-embedding-3-small",
        timeout_seconds: float = 15.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        payload = {
            "model": self._model,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers=headers,
            json=payload,
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        data = response.json().get("data", [])
        embeddings = [item.get("embedding", []) for item in data]
        return [[float(value) for value in embedding] for embedding in embeddings]


class RedisMemoryStorage(StorageBackend):
    """Redis-backed storage for CrewAI unified memory.

    This implementation keeps the vector store lightweight by persisting records in Redis
    and performing cosine similarity ranking in application code. It avoids introducing
    another database while still giving us durable long-term memory.
    """

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        namespace: str = "tribultz:crewai:memory",
        ttl_seconds: int | None = None,
    ) -> None:
        self._client = Redis.from_url(redis_url or settings.REDIS_URL, decode_responses=True)
        self._namespace = namespace.rstrip(":")
        self._ttl_seconds = ttl_seconds if ttl_seconds is not None else settings.CREW_MEMORY_TTL_SECONDS
        self.write_lock = RLock()

    def _record_key(self, record_id: str) -> str:
        return f"{self._namespace}:record:{record_id}"

    def _iter_record_keys(self) -> Iterable[str]:
        yield from self._client.scan_iter(match=f"{self._namespace}:record:*")

    @staticmethod
    def _serialize_record(record: MemoryRecord) -> str:
        return record.model_dump_json()

    def _apply_ttl(self, key: str, value: str) -> None:
        if self._ttl_seconds > 0:
            self._client.setex(key, self._ttl_seconds, value)
            return
        self._client.set(key, value)

    @staticmethod
    def _deserialize_record(raw: str | None) -> MemoryRecord | None:
        if not raw:
            return None
        data = json.loads(raw)
        data["created_at"] = _datetime_from_iso(data.get("created_at")).isoformat()
        data["last_accessed"] = _datetime_from_iso(data.get("last_accessed")).isoformat()
        return MemoryRecord.model_validate(data)

    @staticmethod
    def _matches_scope(record: MemoryRecord, scope_prefix: str | None) -> bool:
        if not scope_prefix:
            return True
        prefix = _normalize_scope(scope_prefix)
        scope = _normalize_scope(record.scope)
        return scope == prefix or scope.startswith(f"{prefix}/")

    @staticmethod
    def _matches_categories(record: MemoryRecord, categories: list[str] | None) -> bool:
        return not categories or any(category in record.categories for category in categories)

    @staticmethod
    def _matches_metadata(record: MemoryRecord, metadata_filter: dict[str, Any] | None) -> bool:
        return not metadata_filter or all(record.metadata.get(key) == value for key, value in metadata_filter.items())

    def save(self, records: list[MemoryRecord]) -> None:
        if not records:
            return
        pipe = self._client.pipeline()
        for record in records:
            key = self._record_key(record.id)
            value = self._serialize_record(record)
            if self._ttl_seconds > 0:
                pipe.setex(key, self._ttl_seconds, value)
            else:
                pipe.set(key, value)
        pipe.execute()

    def search(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        matches: list[tuple[MemoryRecord, float]] = []
        for key in self._iter_record_keys():
            record = self._deserialize_record(cast(str | None, self._client.get(key)))
            if record is None:
                continue
            if not self._matches_scope(record, scope_prefix):
                continue
            if not self._matches_categories(record, categories):
                continue
            if not self._matches_metadata(record, metadata_filter):
                continue
            similarity = _cosine_similarity(query_embedding, record.embedding or [])
            if similarity >= min_score:
                matches.append((record, similarity))
        matches.sort(key=lambda item: item[1], reverse=True)
        return matches[:limit]

    def delete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        if record_ids:
            keys = [self._record_key(record_id) for record_id in record_ids]
            return cast(int, self._client.delete(*keys))

        to_delete: list[str] = []
        for key in self._iter_record_keys():
            record = self._deserialize_record(cast(str | None, self._client.get(key)))
            if record is None:
                continue
            if not self._matches_scope(record, scope_prefix):
                continue
            if not self._matches_categories(record, categories):
                continue
            if not self._matches_metadata(record, metadata_filter):
                continue
            if older_than and record.created_at >= older_than:
                continue
            to_delete.append(key)
        return cast(int, self._client.delete(*to_delete)) if to_delete else 0

    def update(self, record: MemoryRecord) -> None:
        self._apply_ttl(self._record_key(record.id), self._serialize_record(record))

    def get_record(self, record_id: str) -> MemoryRecord | None:
        return self._deserialize_record(cast(str | None, self._client.get(self._record_key(record_id))))

    def list_records(
        self,
        scope_prefix: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        records: list[MemoryRecord] = []
        for key in self._iter_record_keys():
            record = self._deserialize_record(cast(str | None, self._client.get(key)))
            if record is not None and self._matches_scope(record, scope_prefix):
                records.append(record)
        records.sort(key=lambda item: item.created_at, reverse=True)
        return records[offset : offset + limit]

    def get_scope_info(self, scope: str) -> ScopeInfo:
        records = self.list_records(scope_prefix=scope, limit=100000, offset=0)
        categories = sorted({category for record in records for category in record.categories})
        child_scopes = sorted({
            _normalize_scope(record.scope)
            for record in records
            if _normalize_scope(record.scope) != _normalize_scope(scope)
        })
        return ScopeInfo(
            path=_normalize_scope(scope),
            record_count=len(records),
            categories=categories,
            oldest_record=min((record.created_at for record in records), default=None),
            newest_record=max((record.created_at for record in records), default=None),
            child_scopes=child_scopes,
        )

    def list_scopes(self, parent: str = "/") -> list[str]:
        parent_scope = _normalize_scope(parent)
        scopes = set()
        for record in self.list_records(limit=100000):
            scope = _normalize_scope(record.scope)
            if scope == parent_scope:
                continue
            if parent_scope == "/" or scope.startswith(f"{parent_scope}/"):
                scopes.add(scope)
        return sorted(scopes)

    def list_categories(self, scope_prefix: str | None = None) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.list_records(scope_prefix=scope_prefix, limit=100000):
            for category in record.categories:
                counts[category] = counts.get(category, 0) + 1
        return counts

    def count(self, scope_prefix: str | None = None) -> int:
        return len(self.list_records(scope_prefix=scope_prefix, limit=100000))

    def reset(self, scope_prefix: str | None = None) -> None:
        self.delete(scope_prefix=scope_prefix)

    async def asave(self, records: list[MemoryRecord]) -> None:
        self.save(records)

    async def asearch(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        return self.search(
            query_embedding,
            scope_prefix=scope_prefix,
            categories=categories,
            metadata_filter=metadata_filter,
            limit=limit,
            min_score=min_score,
        )

    async def adelete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return self.delete(
            scope_prefix=scope_prefix,
            categories=categories,
            record_ids=record_ids,
            older_than=older_than,
            metadata_filter=metadata_filter,
        )

    def touch_records(self, record_ids: list[str]) -> None:
        for record_id in record_ids:
            record = self.get_record(record_id)
            if record is None:
                continue
            updated = record.model_copy(update={"last_accessed": datetime.now(UTC)})
            self.update(updated)

    def get_record_ttl_seconds(self, record_id: str) -> int:
        return cast(int, self._client.ttl(self._record_key(record_id)))


class ScopedCrewMemory:
    """Adapter that constrains recall/save to well-defined CrewAI memory scopes."""

    def __init__(
        self,
        *,
        memory: Any,
        recall_scopes: list[str],
        write_scope: str,
        default_categories: list[str] | None = None,
        default_metadata: dict[str, Any] | None = None,
        source: str | None = None,
        read_only: bool = False,
    ) -> None:
        self._memory = memory
        self._recall_scopes = [_normalize_scope(scope) for scope in recall_scopes]
        self._write_scope = _normalize_scope(write_scope)
        self._default_categories = default_categories or []
        self._default_metadata = default_metadata or {}
        self._source = source
        self._read_only = read_only

    def recall(self, query: str, limit: int = 10, **kwargs: Any) -> list[MemoryMatch]:
        merged: list[MemoryMatch] = []
        seen_ids: set[str] = set()
        for scope in self._recall_scopes:
            matches = self._memory.recall(
                query,
                scope=scope,
                limit=limit * 2,
                **kwargs,
            )
            for match in matches:
                if match.record.id in seen_ids:
                    continue
                seen_ids.add(match.record.id)
                merged.append(match)
        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[:limit]

    def remember(
        self,
        content: str,
        categories: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        importance: float | None = None,
        **kwargs: Any,
    ) -> Any:
        if self._read_only:
            return None
        merged_categories = list(dict.fromkeys([*self._default_categories, *(categories or [])]))
        merged_metadata = {**self._default_metadata, **(metadata or {})}
        return self._memory.remember(
            content,
            scope=self._write_scope,
            categories=merged_categories,
            metadata=merged_metadata,
            importance=importance,
            source=self._source,
            **kwargs,
        )

    def remember_many(
        self,
        contents: list[str],
        categories: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        importance: float | None = None,
        **kwargs: Any,
    ) -> list[Any]:
        if self._read_only or not contents:
            return []
        merged_categories = list(dict.fromkeys([*self._default_categories, *(categories or [])]))
        merged_metadata = {**self._default_metadata, **(metadata or {})}
        return self._memory.remember_many(
            contents,
            scope=self._write_scope,
            categories=merged_categories,
            metadata=merged_metadata,
            importance=importance,
            source=self._source,
            **kwargs,
        )

    def extract_memories(self, content: str) -> list[str]:
        return self._memory.extract_memories(content)

    def drain_writes(self) -> None:
        if hasattr(self._memory, "drain_writes"):
            self._memory.drain_writes()

    def close(self) -> None:
        if hasattr(self._memory, "close"):
            self._memory.close()


def build_openai_compatible_embedder() -> OpenAICompatibleEmbedder:
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to initialize CrewAI memory embeddings")
    return OpenAICompatibleEmbedder(
        base_url=settings.OPENROUTER_BASE_URL,
        api_key=api_key,
    )


def merge_scored_matches(matches: list[MemoryMatch], limit: int) -> list[MemoryMatch]:
    by_id: dict[str, MemoryMatch] = {}
    for match in matches:
        current = by_id.get(match.record.id)
        if current is None or match.score > current.score:
            by_id[match.record.id] = match
    merged = sorted(by_id.values(), key=lambda item: item.score, reverse=True)
    return merged[:limit]


def recall_across_scopes(
    *,
    memory: Any,
    query: str,
    scopes: list[str],
    limit: int = 10,
    categories: list[str] | None = None,
) -> list[MemoryMatch]:
    matches: list[MemoryMatch] = []
    for scope in scopes:
        for record, semantic_score in memory._storage.search(  # pyright: ignore[reportPrivateUsage]
            memory._embedder([query])[0],  # pyright: ignore[reportPrivateUsage]
            scope_prefix=scope,
            categories=categories,
            limit=limit * 2,
            min_score=0.0,
        ):
            composite, reasons = compute_composite_score(record, semantic_score, memory._config)  # pyright: ignore[reportPrivateUsage]
            matches.append(MemoryMatch(record=record, score=composite, match_reasons=reasons))
    return merge_scored_matches(matches, limit)
