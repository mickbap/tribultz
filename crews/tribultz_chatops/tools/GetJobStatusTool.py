from __future__ import annotations

# Stub — chatops crew not active in production (chat feature deactivated post-S22).
# Integrate with jobs table (app.models.jobs.Job) if crew is re-enabled.

def run_get_job_status(*, tenant_id: str, user_id: str, job_id: str) -> str:
    """Return job status/result string for a given job_id scoped to tenant.

    Not implemented: chatops crew is inactive. Raises on all calls.
    """
    raise NotImplementedError("Chatops crew inactive — query jobs table with tenant_id guard to enable.")
