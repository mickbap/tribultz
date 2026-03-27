from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.config import settings
from app.services.persistence.interfaces import AgentStateStore, IdempotencyStore


class RedisStateStore(AgentStateStore, IdempotencyStore):
    def __init__(self, redis_url: str | None = None, default_ttl_seconds: int = 3600) -> None:
        self._client = Redis.from_url(redis_url or settings.REDIS_URL, decode_responses=True)
        self._default_ttl_seconds = default_ttl_seconds

    def set_state(
        self,
        *,
        transaction_id: str,
        agent_id: str,
        task_id: str,
        state: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        key = self._state_key(transaction_id=transaction_id, agent_id=agent_id, task_id=task_id)
        payload = json.dumps(state, default=str)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl_seconds
        self._client.setex(key, ttl, payload)

    def get_state(
        self,
        *,
        transaction_id: str,
        agent_id: str,
        task_id: str,
    ) -> dict[str, Any] | None:
        key = self._state_key(transaction_id=transaction_id, agent_id=agent_id, task_id=task_id)
        raw = self._client.get(key)
        if isinstance(raw, bytes):
            return json.loads(raw.decode("utf-8"))
        if isinstance(raw, str):
            return json.loads(raw)
        return None

    def get_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        key = self._operation_key(transaction_id=transaction_id, operation=operation)
        raw = self._client.get(key)
        if isinstance(raw, bytes):
            record = json.loads(raw.decode("utf-8"))
        elif isinstance(raw, str):
            record = json.loads(raw)
        else:
            return None
        if record.get("request_hash") != request_hash:
            raise ValueError("transaction_id already used with different payload")
        result = record.get("result")
        return result if isinstance(result, dict) else None

    def save_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
        result: dict[str, Any],
    ) -> None:
        key = self._operation_key(transaction_id=transaction_id, operation=operation)
        payload = json.dumps({"request_hash": request_hash, "result": result}, default=str)
        self._client.setex(key, self._default_ttl_seconds, payload)

    @staticmethod
    def _state_key(*, transaction_id: str, agent_id: str, task_id: str) -> str:
        return f"crew:state:{transaction_id}:{agent_id}:{task_id}"

    @staticmethod
    def _operation_key(*, transaction_id: str, operation: str) -> str:
        return f"tools:idempotency:{transaction_id}:{operation}"
