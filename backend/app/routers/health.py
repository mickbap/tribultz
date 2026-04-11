"""Health-check router — liveness + deep readiness probe.

GET /health          → liveness   (sempre 200, sem dependências)
GET /health/ready    → readiness  (DB + Redis + Asaas + AI Engine)
GET /health/deep     → alias de /health/ready (convenção Magalu Cloud)
"""

from __future__ import annotations

import logging
import time
from typing import Literal

import httpx
import redis as redis_lib
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.services.asaas_service import resolve_asaas_v3_base_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# ── Response models ───────────────────────────────────────────────────────────

ServiceStatus = Literal["ok", "degraded", "unreachable", "unconfigured"]


class DeepHealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    db: ServiceStatus
    redis: ServiceStatus
    asaas_api: ServiceStatus
    ai_engine: ServiceStatus
    latency_ms: int


# ── Probe helpers ─────────────────────────────────────────────────────────────

def _probe_db() -> ServiceStatus:
    """Try a lightweight SELECT 1 against PostgreSQL."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return "ok"
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Health: DB probe failed — %s", exc)
        return "unreachable"


def _probe_redis() -> ServiceStatus:
    """PING the Redis instance."""
    try:
        client = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
        client.ping()
        return "ok"
    except Exception as exc:
        logger.warning("Health: Redis probe failed — %s", exc)
        return "unreachable"


def _probe_asaas() -> ServiceStatus:
    """Hit Asaas /finance/balance (timeout 3s).

    Returns 'unconfigured' when ASAAS_API_KEY is blank so monitoring
    alerts are silent when the service is intentionally disabled.
    """
    if not settings.ASAAS_API_KEY:
        return "unconfigured"
    base = resolve_asaas_v3_base_url(settings.ASAAS_ENVIRONMENT)
    try:
        resp = httpx.get(
            f"{base}/finance/balance",
            headers={"access_token": settings.ASAAS_API_KEY},
            timeout=3.0,
        )
        # 200 / 401 / 403 / 404 all mean the API gateway is reachable
        # 404 can occur when the account has no balance record yet
        if resp.status_code in (200, 401, 403, 404):
            return "ok"
        logger.warning("Health: Asaas returned HTTP %s", resp.status_code)
        return "degraded"
    except Exception as exc:
        logger.warning("Health: Asaas probe failed — %s", exc)
        return "unreachable"


def _probe_ai_engine() -> ServiceStatus:
    """GET OpenRouter /models (timeout 3s).

    Returns 'unconfigured' when OPENROUTER_API_KEY is blank.
    """
    if not settings.OPENROUTER_API_KEY:
        return "unconfigured"
    try:
        resp = httpx.get(
            f"{settings.OPENROUTER_BASE_URL}/models",
            headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
            timeout=3.0,
        )
        if resp.status_code in (200, 401, 403):
            return "ok"
        logger.warning("Health: OpenRouter returned HTTP %s", resp.status_code)
        return "degraded"
    except Exception as exc:
        logger.warning("Health: AI engine probe failed — %s", exc)
        return "unreachable"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.api_route("", methods=["GET", "HEAD"], summary="Liveness probe")
def healthcheck():
    """Fast liveness probe — no dependency checks.

    Usado por Docker HEALTHCHECK, Kubernetes liveness probe e
    load-balancers que precisam de resposta imediata.
    """
    return {"status": "ok"}


@router.get(
    "/ready",
    response_model=DeepHealthResponse,
    summary="Deep readiness probe",
)
def readiness() -> DeepHealthResponse:
    """Deep readiness probe — verifica todas as dependências críticas.

    status: "ok"       → todos os serviços responderam
    status: "degraded" → serviços opcionais (Asaas, AI) fora
    status: "error"    → serviços críticos (DB, Redis) fora

    Todas as probes têm timeout curto: endpoint resolve em < 4s.
    """
    t0 = time.monotonic()

    db_status    = _probe_db()
    redis_status = _probe_redis()
    asaas_status = _probe_asaas()
    ai_status    = _probe_ai_engine()

    latency_ms = int((time.monotonic() - t0) * 1000)

    critical_ok = db_status == "ok" and redis_status == "ok"
    optional_ok = asaas_status in ("ok", "unconfigured") and \
                  ai_status in ("ok", "unconfigured")

    if not critical_ok:
        overall: Literal["ok", "degraded", "error"] = "error"
    elif not optional_ok:
        overall = "degraded"
    else:
        overall = "ok"

    return DeepHealthResponse(
        status=overall,
        db=db_status,
        redis=redis_status,
        asaas_api=asaas_status,
        ai_engine=ai_status,
        latency_ms=latency_ms,
    )


@router.get(
    "/deep",
    response_model=DeepHealthResponse,
    summary="Deep readiness probe (alias Magalu Cloud)",
)
def deep_health() -> DeepHealthResponse:
    """Alias de /health/ready — convenção de monitoramento Magalu Cloud."""
    return readiness()
