"""Health-check router — liveness + deep readiness probe.

GET /health          → liveness   (sempre 200, sem dependências)
GET /health/ready    → readiness  (DB + Redis + Asaas + AI Engine)
GET /health/deep     → alias de /health/ready (convenção Magalu Cloud)
"""

from __future__ import annotations

import logging
import smtplib
import time
from typing import Literal

import boto3
import httpx
import redis as redis_lib
from botocore.config import Config as BotoConfig
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
    hubspot: ServiceStatus
    email: ServiceStatus
    storage: ServiceStatus
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


def _probe_hubspot() -> ServiceStatus:
    """Hit HubSpot /crm/v3/objects/contacts?limit=1 (timeout 3s).

    Returns 'unconfigured' when HUBSPOT_ENABLED=false or token is blank,
    para evitar alertas falsos quando a integração está intencionalmente
    desativada (ex: ambientes de staging sem CRM).
    """
    if not settings.HUBSPOT_ENABLED or not settings.HUBSPOT_PRIVATE_APP_TOKEN:
        return "unconfigured"
    try:
        resp = httpx.get(
            f"{settings.HUBSPOT_API_BASE_URL}/crm/v3/objects/contacts",
            params={"limit": 1},
            headers={
                "Authorization": f"Bearer {settings.HUBSPOT_PRIVATE_APP_TOKEN}",
            },
            timeout=3.0,
        )
        # 200 OK ; 401/403 → token problema mas gateway responde (reachable)
        if resp.status_code in (200, 401, 403):
            return "ok"
        logger.warning("Health: HubSpot returned HTTP %s", resp.status_code)
        return "degraded"
    except Exception as exc:
        logger.warning("Health: HubSpot probe failed — %s", exc)
        return "unreachable"


def _probe_email() -> ServiceStatus:
    """Conecta no relay SMTP (Resend em produção) e faz EHLO (timeout 3s).

    Mesma condição de no-op do email_service: 'unconfigured' quando
    EMAIL_VERIFICATION_ENABLED=false ou SMTP_HOST vazio. Não autentica nem
    envia — apenas valida que o gateway SMTP está alcançável.
    """
    if not settings.EMAIL_VERIFICATION_ENABLED or not settings.SMTP_HOST:
        return "unconfigured"
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=3.0) as server:
            server.ehlo()
        return "ok"
    except Exception as exc:
        logger.warning("Health: SMTP/email probe failed — %s", exc)
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


def _probe_s3() -> ServiceStatus:
    """HEAD the configured object-storage bucket (boto3 head_bucket, timeout 3s).

    O storage guarda XMLs enviados, bundles de export e evidências — é crítico:
    sem ele não há validação com evidência. Retorna 'unconfigured' quando o
    endpoint/bucket estão em branco, para não alertar em ambientes sem object
    storage (dev). Qualquer falha real (endpoint morto, timeout, credencial
    inválida) é 'unreachable' — o Uptime Monitor precisa gritar.
    """
    if not settings.S3_ENDPOINT or not settings.S3_BUCKET:
        return "unconfigured"
    try:
        client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path" if settings.S3_FORCE_PATH_STYLE else "virtual"},
                connect_timeout=3,
                read_timeout=3,
                retries={"max_attempts": 0},
            ),
        )
        client.head_bucket(Bucket=settings.S3_BUCKET)
        return "ok"
    except Exception as exc:
        logger.warning("Health: object storage probe failed — %s", exc)
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

    db_status      = _probe_db()
    redis_status   = _probe_redis()
    asaas_status   = _probe_asaas()
    ai_status      = _probe_ai_engine()
    hubspot_status = _probe_hubspot()
    email_status   = _probe_email()
    storage_status = _probe_s3()

    latency_ms = int((time.monotonic() - t0) * 1000)

    # storage é crítico: sem object storage não há validação com evidência.
    # 'unconfigured' (dev sem storage) não alerta; 'unreachable' derruba o status.
    critical_ok = (
        db_status == "ok"
        and redis_status == "ok"
        and storage_status in ("ok", "unconfigured")
    )
    optional_ok = (
        asaas_status   in ("ok", "unconfigured") and
        ai_status      in ("ok", "unconfigured") and
        hubspot_status in ("ok", "unconfigured") and
        email_status   in ("ok", "unconfigured")
    )

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
        hubspot=hubspot_status,
        email=email_status,
        storage=storage_status,
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
