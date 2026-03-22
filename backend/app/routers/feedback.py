"""Feedback router — in-platform customer feedback channel."""

import logging
from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackCreate, FeedbackRead
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("/", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
def create_feedback(
    data: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    tenant_id = current_user["tenant_id"]

    feedback = Feedback(
        tenant_id=tenant_id,
        user_id=user_id,
        category=data.category,
        message=data.message,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    logger.info(
        "feedback_created",
        extra={"user_id": str(user_id), "category": data.category},
    )

    return FeedbackRead(
        id=cast(UUID, feedback.id),
        tenant_id=cast(UUID, feedback.tenant_id),
        user_id=cast(UUID, feedback.user_id),
        category=cast(str, feedback.category),
        message=cast(str, feedback.message),
        created_at=feedback.created_at,  # type: ignore[arg-type]
    )


@router.get("/", response_model=list[FeedbackRead])
def list_feedback(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    tenant_id = current_user["tenant_id"]
    stmt = (
        select(Feedback)
        .where(Feedback.tenant_id == tenant_id)
        .order_by(Feedback.created_at.desc())  # type: ignore[union-attr]
        .limit(50)
    )
    rows = db.execute(stmt).scalars().all()
    return [
        FeedbackRead(
            id=cast(UUID, r.id),
            tenant_id=cast(UUID, r.tenant_id),
            user_id=cast(UUID, r.user_id),
            category=cast(str, r.category),
            message=cast(str, r.message),
            created_at=r.created_at,  # type: ignore[arg-type]
        )
        for r in rows
    ]
