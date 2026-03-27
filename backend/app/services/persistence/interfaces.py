from __future__ import annotations

from typing import Any, Protocol


class AgentStateStore(Protocol):
    def set_state(
        self,
        *,
        transaction_id: str,
        agent_id: str,
        task_id: str,
        state: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None: ...

    def get_state(
        self,
        *,
        transaction_id: str,
        agent_id: str,
        task_id: str,
    ) -> dict[str, Any] | None: ...


class FiscalContextStore(Protocol):
    def append_context(
        self,
        *,
        transaction_id: str,
        tenant_id: str | None,
        agent_id: str,
        task_id: str,
        context: dict[str, Any],
    ) -> None: ...

    def list_context(self, *, transaction_id: str) -> list[dict[str, Any]]: ...


class IdempotencyStore(Protocol):
    def get_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
    ) -> dict[str, Any] | None: ...

    def save_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
        result: dict[str, Any],
    ) -> None: ...


class IdempotencyRunner(Protocol):
    def __call__(self) -> dict[str, Any]: ...
