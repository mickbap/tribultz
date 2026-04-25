from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.news import News

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/news", tags=["news"])

NewsCategory = Literal["Feature", "Fix", "Security"]


class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    category: NewsCategory
    created_at: datetime


class NewsCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=3, max_length=2000)
    category: NewsCategory = "Feature"


@router.get(
    "",
    response_model=list[NewsResponse],
    summary="Listar novidades do sistema",
    description="Retorna as N entradas mais recentes do changelog em ordem decrescente de data (default 10, máximo 50).",
)
def list_news(
    db: Session = Depends(get_db),
    limit: int = Query(10, ge=1, le=50, description="Quantas entradas retornar (1-50)"),
) -> list[News]:
    stmt = select(News).order_by(News.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=NewsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publicar nova entrada de changelog (uso interno via GitHub Actions)",
    description=(
        "Endpoint protegido por token. Idempotente: se já existe uma entrada com o "
        "mesmo título nos últimos 30 dias, retorna a existente (200) em vez de criar."
    ),
)
def create_news(
    payload: NewsCreateRequest,
    response: Response,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> News:
    # ── Auth via token interno (Bearer) ──
    expected_token = settings.NEWS_PUBLISH_TOKEN
    if not expected_token:
        # Em ambientes que não configuraram o token, recusa por default
        # (evita que produção fique aberta caso o secret não tenha sido populado).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="News publishing is not configured on this server.",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_token = authorization.removeprefix("Bearer ").strip()
    if provided_token != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid news publish token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Idempotência: dedupe por título nos últimos 30 dias ──
    from datetime import timedelta, timezone as _tz
    cutoff = datetime.now(_tz.utc) - timedelta(days=30)
    existing = db.scalar(
        select(News)
        .where(News.title == payload.title)
        .where(News.created_at >= cutoff)
        .order_by(News.created_at.desc())
        .limit(1)
    )
    if existing is not None:
        logger.info("create_news: duplicate title within 30d, returning existing %s", existing.id)
        response.status_code = status.HTTP_200_OK
        return existing

    row = News(
        title=payload.title,
        description=payload.description,
        category=payload.category,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info("create_news: published id=%s category=%s", row.id, payload.category)
    return row
