from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.news import News

router = APIRouter(prefix="/api/v1/news", tags=["news"])


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    category: Literal["Feature", "Fix", "Security"]
    created_at: datetime


@router.get(
    "",
    response_model=list[NewsResponse],
    summary="Listar novidades do sistema",
    description="Retorna as 10 entradas mais recentes do changelog em ordem decrescente de data.",
)
def list_news(db: Session = Depends(get_db)) -> list[News]:
    stmt = select(News).order_by(News.created_at.desc()).limit(10)
    return list(db.scalars(stmt).all())
