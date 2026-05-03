"""NCM Auto-classify router.

POST /api/v1/public/ncm/suggest  — freemium, rate-limited (10 req/min, 50 req/dia por IP)
POST /api/v1/ncm/batch           — autenticado, plano Profissional+
"""

from __future__ import annotations

import logging
from typing import Optional

import redis as _redis
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.api.plan_gate import require_plan
from app.config import settings
from app.models.auth import User
from app.services import ncm_classifier
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ncm"])

_rate_limiter = RateLimiter()

# Redis compartilhado para cache do classifier
_redis_client: _redis.Redis | None = None
if settings.REDIS_URL:
    try:
        _redis_client = _redis.from_url(settings.REDIS_URL, decode_responses=True)
        _redis_client.ping()
    except Exception:  # noqa: BLE001
        _redis_client = None


# ── Schemas ───────────────────────────────────────────────────────────────────

class NcmSuggestRequest(BaseModel):
    descricao: str = Field(..., min_length=3, max_length=500, description="Descrição do produto")


class NcmSuggestResponse(BaseModel):
    ncm: str
    confidence: float
    cClassTrib: Optional[str]
    cest: Optional[str]
    reasoning: str
    cached: bool


class NcmBatchItem(BaseModel):
    id: Optional[str] = None
    descricao: str = Field(..., min_length=3, max_length=500)


class NcmBatchRequest(BaseModel):
    items: list[NcmBatchItem] = Field(..., min_length=1, max_length=100)


class NcmBatchResultItem(BaseModel):
    id: Optional[str]
    descricao: str
    ncm: str
    confidence: float
    cClassTrib: Optional[str]
    cest: Optional[str]
    reasoning: str
    cached: bool
    error: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/api/v1/public/ncm/suggest",
    response_model=NcmSuggestResponse,
    summary="Sugerir NCM a partir de descrição do produto (freemium)",
    description=(
        "Classifica automaticamente o NCM (8 dígitos) a partir da descrição do produto "
        "usando IA fiscal. Rate limit: 10 req/min por IP. Cache Redis: 7 dias."
    ),
)
def ncm_suggest_public(body: NcmSuggestRequest, request: Request) -> NcmSuggestResponse:
    client_ip = request.client.host if request.client else "unknown"
    _rate_limiter.check_or_raise(f"ncm_suggest:{client_ip}")

    try:
        result = ncm_classifier.suggest(body.descricao, _redis_client)
    except Exception as exc:  # noqa: BLE001
        logger.exception("NCM suggest failed for descricao=%r", body.descricao[:50])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Serviço de classificação temporariamente indisponível.",
        ) from exc

    return NcmSuggestResponse(**result)


@router.post(
    "/api/v1/ncm/batch",
    response_model=list[NcmBatchResultItem],
    summary="Classificação NCM em lote (Profissional+)",
    description="Classifica até 100 produtos por chamada. Disponível nos planos Profissional, Empresarial e Contador.",
    dependencies=[Depends(require_plan("profissional", "empresarial", "contador"))],
)
def ncm_batch(
    body: NcmBatchRequest,
    current_user: User = Depends(get_current_user),
) -> list[NcmBatchResultItem]:
    results: list[NcmBatchResultItem] = []
    for item in body.items:
        try:
            r = ncm_classifier.suggest(item.descricao, _redis_client)
            results.append(NcmBatchResultItem(id=item.id, descricao=item.descricao, **r))
        except Exception as exc:  # noqa: BLE001
            logger.warning("NCM batch item failed: %s — %s", item.descricao[:40], exc)
            results.append(NcmBatchResultItem(
                id=item.id,
                descricao=item.descricao,
                ncm="",
                confidence=0.0,
                cClassTrib=None,
                cest=None,
                reasoning="",
                cached=False,
                error="Classificação indisponível para este item.",
            ))
    return results
