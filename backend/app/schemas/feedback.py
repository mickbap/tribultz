from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


class FeedbackCreate(BaseModel):
    category: Literal["bug", "sugestao", "elogio"]
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Mensagem deve ter no minimo 10 caracteres.")
        if len(v) > 2000:
            raise ValueError("Mensagem deve ter no maximo 2000 caracteres.")
        return v


class FeedbackRead(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID
    category: str
    message: str
    created_at: datetime

    class Config:
        from_attributes = True
