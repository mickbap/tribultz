from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from uuid import UUID

class JobEvidence(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    type: Literal["job", "audit"]
    job_id: Optional[UUID] = None
    href: str = ""
    label: str = ""
    payload: Optional[dict] = None

class ChatResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    conversation_id: UUID
    response_markdown: str
    evidence: List[JobEvidence]
