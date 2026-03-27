from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.database import SessionLocal
from app.services.persistence.interfaces import FiscalContextStore, IdempotencyStore

_FISCAL_CONTEXT_DDL = """
CREATE TABLE IF NOT EXISTS crew_fiscal_context (
    id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(120) NOT NULL,
    tenant_id UUID NULL,
    agent_id VARCHAR(120) NOT NULL,
    task_id VARCHAR(120) NOT NULL,
    context JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_crew_fiscal_context_txn ON crew_fiscal_context(transaction_id, created_at);
"""

_IDEMPOTENCY_DDL = """
CREATE TABLE IF NOT EXISTS tool_transaction_log (
    id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(120) NOT NULL,
    operation VARCHAR(160) NOT NULL,
    request_hash VARCHAR(128) NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (transaction_id, operation)
);
"""


class PostgresPersistenceStore(FiscalContextStore, IdempotencyStore):
    def append_context(
        self,
        *,
        transaction_id: str,
        tenant_id: str | None,
        agent_id: str,
        task_id: str,
        context: dict[str, Any],
    ) -> None:
        with SessionLocal() as db:
            self._ensure_tables(db)
            db.execute(
                text(
                    """
                    INSERT INTO crew_fiscal_context
                        (transaction_id, tenant_id, agent_id, task_id, context)
                    VALUES
                        (:transaction_id, CAST(:tenant_id AS uuid), :agent_id, :task_id, CAST(:context AS jsonb))
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "context": json.dumps(context, default=str),
                },
            )
            db.commit()

    def list_context(self, *, transaction_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            self._ensure_tables(db)
            rows = db.execute(
                text(
                    """
                    SELECT transaction_id, tenant_id, agent_id, task_id, context, created_at
                    FROM crew_fiscal_context
                    WHERE transaction_id = :transaction_id
                    ORDER BY created_at ASC
                    """
                ),
                {"transaction_id": transaction_id},
            ).fetchall()
        return [
            {
                "transaction_id": str(row.transaction_id),
                "tenant_id": str(row.tenant_id) if row.tenant_id else None,
                "agent_id": str(row.agent_id),
                "task_id": str(row.task_id),
                "context": row.context,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    def get_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            self._ensure_tables(db)
            row = db.execute(
                text(
                    """
                    SELECT request_hash, result
                    FROM tool_transaction_log
                    WHERE transaction_id = :transaction_id
                      AND operation = :operation
                    """
                ),
                {"transaction_id": transaction_id, "operation": operation},
            ).fetchone()
        if not row:
            return None
        if row.request_hash != request_hash:
            raise ValueError("transaction_id already used with different payload")
        return row.result if isinstance(row.result, dict) else {}

    def save_operation_result(
        self,
        *,
        transaction_id: str,
        operation: str,
        request_hash: str,
        result: dict[str, Any],
    ) -> None:
        with SessionLocal() as db:
            self._ensure_tables(db)
            db.execute(
                text(
                    """
                    INSERT INTO tool_transaction_log (transaction_id, operation, request_hash, result)
                    VALUES (:transaction_id, :operation, :request_hash, CAST(:result AS jsonb))
                    ON CONFLICT (transaction_id, operation)
                    DO UPDATE SET
                        request_hash = EXCLUDED.request_hash,
                        result = EXCLUDED.result,
                        updated_at = now()
                    """
                ),
                {
                    "transaction_id": transaction_id,
                    "operation": operation,
                    "request_hash": request_hash,
                    "result": json.dumps(result, default=str),
                },
            )
            db.commit()

    @staticmethod
    def _ensure_tables(db: Any) -> None:
        db.execute(text(_FISCAL_CONTEXT_DDL))
        db.execute(text(_IDEMPOTENCY_DDL))
        db.commit()
