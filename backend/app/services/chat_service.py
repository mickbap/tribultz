from __future__ import annotations

import logging
import json
from typing import Optional, List, Literal, Any, cast
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

from app.models.chat import Conversation, Message
from app.crews.executor import TribultzChatOpsExecutor
from app.services.rate_limit import RateLimiter
from app.schemas.chat import JobEvidence, ChatResult

logger = logging.getLogger(__name__)

Intent = Literal["validate", "unknown"]

def classify_intent(message: str) -> Intent:
    """
    MVP classifier (keyword/regex based).
    """
    m = message.lower()
    if "validate" in m or "validar" in m or "validação" in m:
        return "validate"
    return "unknown"

class ChatService:
    """
    Orchestrates Chat interactions:
      1. Rate Limiting
      2. Conversation Persistence/Ownership logic
      3. Intent Classification
      4. Crew Execution (Task A)
      5. Audit Logging (placeholders)
    """

    def __init__(self, db: Session):
        self.db = db
        self.executor = TribultzChatOpsExecutor() # Can inject dependency if needed
        self.rate_limiter = RateLimiter() # Can inject singleton
        # self.audit = ... 

    async def handle_message(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        message: str,
        conversation_id: Optional[UUID],
    ) -> ChatResult:
        
        # 1. Rate Limit
        self.rate_limiter.check_or_raise(str(user_id))

        # 2. Conversation Check / Create
        if conversation_id:
            # Verify ownership
            conv = self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == tenant_id
                )
            ).scalar_one_or_none()
            
            if not conv:
                # Security: Mismatch returns 404 to avoid leaking existence
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
        else:
            # Create new
            conv = Conversation(
                tenant_id=tenant_id,
                user_id=user_id,
                title=message[:50]  # Simple title
            )
            self.db.add(conv)
            self.db.flush()  # get ID
            conversation_id = cast(UUID, conv.id)

        # Persist User Message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=message
        )
        self.db.add(user_msg)
        
        # 3. Classify & Execute
        intent = classify_intent(message)
        # TODO: Audit chat_message_received (tenant_id, user_id, conversation_id, intent)
        
        response_markdown = ""
        evidence_list: List[JobEvidence] = []

        if intent == "validate":
            # 4. Trigger Task A
            try:
                job_id = await self.executor.trigger_task_a(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    message=message
                )
                
                response_markdown = f"Started validation task for you.\n\n**Job ID**: `{job_id}`"
                evidence_list.append(JobEvidence(
                    type="job",
                    job_id=job_id,
                    href=f"/jobs/{job_id}",
                    label="Validation Job"
                ))
                
                # TODO: Audit chat_task_triggered (job_id)

            except Exception as e:
                logger.error(f"Chat execution error: {e}")
                response_markdown = "I encountered an error trying to start validation. Please try again."
                # Evidence empty on error
        
        else:
            # Fallback
            response_markdown = "I'm not sure how to help with that. Currently I can assist with **validating invoices** (CBS/IBS)."
        
        # 5. Persist Assistant Response
        # Store evidence in metadata
        evidence_dicts = [e.model_dump() for e in evidence_list]
        # JSON serialize UUIDs
        def uuid_serializer(obj: Any) -> Any:
            if isinstance(obj, UUID):
                return str(obj)
            return obj

        assistant_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=response_markdown,
            metadata_=json.loads(json.dumps({"evidence": evidence_dicts}, default=uuid_serializer))
        )
        self.db.add(assistant_msg)
        self.db.commit()

        return ChatResult(
            conversation_id=conversation_id,
            response_markdown=response_markdown,
            evidence=evidence_list
        )
