from __future__ import annotations

# MVP tool skeleton. Must return a string.
# In CrewAI, prefer using: from crewai_tools import tool

from uuid import uuid4

def run_trigger_task_a(*, tenant_id: str, user_id: str, message: str, dry_run: bool = False) -> str:
    """
    TODO: integrate with your internal Task A trigger.
    Return job_id as string.
    """
    if dry_run:
        return str(uuid4())
    raise NotImplementedError("Integrate with real Task A trigger and return job_id.")
