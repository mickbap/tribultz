from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, UUID4
from typing import Optional, List, cast
from uuid import UUID

from app.api.deps import get_current_user
from app.database import get_db
from app.models.auth import User
from app.services.chat_service import ChatService
from app.schemas.chat import JobEvidence
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[UUID4] = None

class ChatMessageResponse(BaseModel):
    conversation_id: UUID4
    response_markdown: str
    evidence: List[JobEvidence] = Field(default_factory=list)

@router.post("/message", response_model=ChatMessageResponse)
async def post_chat_message(
    payload: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    MVP strict contract:
      - accepts ONLY message + optional conversation_id
      - tenant_id MUST come from JWT/current_user, never from payload
      - mismatch tenant/user for conversation_id MUST return 404
      - always returns {conversation_id, response_markdown, evidence[]}
    """
    service = ChatService(db=db)
    tenant_id = cast(UUID, current_user.tenant_id)
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context (missing tenant).",
        )

    result = await service.handle_message(
        tenant_id=tenant_id,
        user_id=cast(UUID, current_user.id),
        message=payload.message,
        conversation_id=payload.conversation_id,
    )

    return ChatMessageResponse(
        conversation_id=result.conversation_id,
        response_markdown=result.response_markdown,
        evidence=result.evidence
    )
