from __future__ import annotations

# Stub — chatops crew not active in production (chat feature deactivated post-S22).
# Integrate with Celery task_a_validate if crew is re-enabled.

from uuid import uuid4

def run_trigger_task_a(*, tenant_id: str, user_id: str, message: str, dry_run: bool = False) -> str:
    """Trigger Task A validation job for a tenant.

    Not implemented: chatops crew is inactive. Raises on non-dry-run calls.
    """
    if dry_run:
        return str(uuid4())
    raise NotImplementedError("Chatops crew inactive — wire to task_a_validate Celery task to enable.")
