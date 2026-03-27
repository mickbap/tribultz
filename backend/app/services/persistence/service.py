from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.persistence.interfaces import (
    AgentStateStore,
    FiscalContextStore,
    IdempotencyRunner,
    IdempotencyStore,
)


class CrewPersistenceService:
    def __init__(
        self,
        *,
        state_store: AgentStateStore,
        fiscal_context_store: FiscalContextStore,
        fast_idempotency_store: IdempotencyStore,
        durable_idempotency_store: IdempotencyStore,
    ) -> None:
        self._state_store = state_store
        self._fiscal_context_store = fiscal_context_store
        self._fast_idempotency_store = fast_idempotency_store
        self._durable_idempotency_store = durable_idempotency_store

    def record_handoff(
        self,
        *,
        transaction_id: str,
        tenant_id: str | None,
        agent_id: str,
        task_id: str,
        task_status: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        state_payload = {"task_status": task_status, "payload": payload or {}}
        self._state_store.set_state(
            transaction_id=transaction_id,
            agent_id=agent_id,
            task_id=task_id,
            state=state_payload,
        )
        self._fiscal_context_store.append_context(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            agent_id=agent_id,
            task_id=task_id,
            context=state_payload,
        )

    def run_idempotent(
        self,
        *,
        operation: str,
        transaction_id: str | None,
        payload: dict[str, Any],
        runner: IdempotencyRunner,
    ) -> dict[str, Any]:
        if not transaction_id:
            return runner()
        request_hash = _stable_hash(payload)
        cached = self._fast_idempotency_store.get_operation_result(
            transaction_id=transaction_id,
            operation=operation,
            request_hash=request_hash,
        )
        if cached is not None:
            return cached
        durable = self._durable_idempotency_store.get_operation_result(
            transaction_id=transaction_id,
            operation=operation,
            request_hash=request_hash,
        )
        if durable is not None:
            self._fast_idempotency_store.save_operation_result(
                transaction_id=transaction_id,
                operation=operation,
                request_hash=request_hash,
                result=durable,
            )
            return durable
        result = runner()
        self._durable_idempotency_store.save_operation_result(
            transaction_id=transaction_id,
            operation=operation,
            request_hash=request_hash,
            result=result,
        )
        self._fast_idempotency_store.save_operation_result(
            transaction_id=transaction_id,
            operation=operation,
            request_hash=request_hash,
            result=result,
        )
        return result


def _stable_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
