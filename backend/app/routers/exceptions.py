"""Exception requests router — stub (table not yet migrated)."""

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User

router = APIRouter(prefix="/api/v1/exceptions", tags=["exceptions"])


class ExceptionRequestResponse(BaseModel):
    id: str
    tenant_id: str
    job_id: str
    finding_id: str
    rule_id: str
    justification: str
    status: str
    created_by: str
    created_at: str
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    decision_comment: Optional[str] = None


@router.get("", response_model=list[ExceptionRequestResponse])
def list_exception_requests(
    db: Session = Depends(get_db),  # noqa: ARG001
    current_user: User = Depends(get_current_user),  # noqa: ARG001
) -> list[Any]:
    """List exception requests for the tenant. Table migration pending — returns empty list."""
    return []
