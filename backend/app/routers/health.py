"""Health-check router — liveness + deep readiness probe.

GET /health          → liveness   (sempre 200, sem dependências)
GET /health/ready    → readiness  (DB + Redis + Asaas + AI Engine)
GET /health/deep     → alias de /health/ready (convenção Magalu Cloud)
"""

from __future__ import annotations

import logging
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
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
from app.services import regulatory_freshness
from app.services.asaas_service import resolve_asaas_v3_base_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

# ── Response models ───────────────────────────────────────────────────────────

ServiceStatus = Literal["ok", "degraded", "unreachable", "unconfigured"]


class ClassTribFreshnessOut(BaseModel):
    """Evidência temporal da versão regulatória em uso pelo motor (#673).

    ``source_state`` é o campo que torna inequívoca a distinção entre "fonte
    consultada sem mudança" (``match``) e "fonte não verificável"
    (``unverifiable``) — que antes eram o mesmo silêncio.
    """

    status: Literal["ok", "degraded", "stale"]
    source_state: Literal["match", "drift", "unverifiable"]
    #: Versão EMBARCADA na imagem (meta.date do classtrib.json). Não confundir
    #: com "último sync bem-sucedido": ver `sync_execution`.
    bundled_version_date: str | None = None
    bundled_version_age_days: int | None = None
    #: Execução do coletor. `unobservable` enquanto não existir heartbeat (#674).
    #: Explicitamente ausente — nunca inferida de `source_state == "match"`.
    sync_execution: Literal["unobservable"] = "unobservable"
    local_codes: int = 0
    remote_codes: int | None = None
    detail: str = ""
    codes_added: list[str] = []
    codes_removed: list[str] = []


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
    # #673 — dependência REGULATÓRIA. Default preserva compatibilidade dos
    # consumidores anteriores à instrumentação.
    classtrib: ServiceStatus = "unconfigured"
    classtrib_freshness: ClassTribFreshnessOut | None = None


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


def _probe_classtrib() -> "regulatory_freshness.Freshness | None":
    """Frescor do dado regulatório cClassTrib (#673).

    Devolve o veredito completo (não só um ServiceStatus) porque a evidência —
    data do dado, idade, estado da fonte, códigos divergentes — é o produto
    desta probe. ``None`` quando desligada por configuração.

    Nunca levanta: o módulo já converte qualquer falha de rede em
    ``source_state='unverifiable'``.
    """
    if not settings.CLASSTRIB_FRESHNESS_ENABLED:
        return None
    return regulatory_freshness.current(monotonic=time.monotonic)


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
        # 6s, não 3s: com os probes em paralelo o timeout não custa mais latência
        # total (ela é a do probe mais lento), e o handshake a frio — DNS + TCP até
        # us-east-1 + banner do relay — passava de 3s logo após o deploy. Quente,
        # mede 0,62s de dentro do container.
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=6.0) as server:
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

    # Probes em paralelo (#L2.5). Antes rodavam em série: sete chamadas de rede,
    # cada uma com timeout próprio, somando 2–5s de latência. No cold start —
    # logo após o deploy, com a aplicação ainda aquecendo — a soma estourava o
    # timeout de 3s do probe SMTP e o endpoint devolvia `degraded` com
    # `email=unreachable`, mesmo com o relay perfeitamente acessível (medido:
    # 0,62s de dentro do container, já quente). Ou seja, TODO deploy produzia uma
    # janela de degradação falsa.
    #
    # São todas I/O bloqueante, então threads resolvem: a latência passa a ser a
    # do probe mais lento, não a soma, e nenhum probe compete com os outros pelo
    # próprio orçamento de tempo.
    _probes = {
        "db": _probe_db,
        "redis": _probe_redis,
        "asaas": _probe_asaas,
        "ai": _probe_ai_engine,
        "hubspot": _probe_hubspot,
        "email": _probe_email,
        "storage": _probe_s3,
        "classtrib": _probe_classtrib,   # #673 — dependência regulatória
    }
    with ThreadPoolExecutor(max_workers=len(_probes)) as _pool:
        _futuros = {nome: _pool.submit(fn) for nome, fn in _probes.items()}
        _r = {}
        for nome, fut in _futuros.items():
            try:
                _r[nome] = fut.result(timeout=10)
            except Exception as exc:  # noqa: BLE001 — probe nunca derruba o endpoint
                logger.warning("Health: probe %s falhou — %s", nome, exc)
                _r[nome] = "unreachable"

    db_status      = _r["db"]
    redis_status   = _r["redis"]
    asaas_status   = _r["asaas"]
    ai_status      = _r["ai"]
    hubspot_status = _r["hubspot"]
    email_status   = _r["email"]
    storage_status = _r["storage"]

    # #673 — a probe devolve o veredito completo; a falha genérica do pool vira
    # string "unreachable", tratada aqui como ausência de evidência.
    _fresh = _r.get("classtrib")
    _fresh = _fresh if isinstance(_fresh, regulatory_freshness.Freshness) else None
    classtrib_status: ServiceStatus = (
        regulatory_freshness.to_service_status(_fresh) if _fresh else "unconfigured"
    )

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
        email_status   in ("ok", "unconfigured") and
        # Dado regulatório velho degrada, mas NUNCA vira `error`: é problema de
        # confiança no dado, não de disponibilidade do serviço.
        classtrib_status in ("ok", "unconfigured")
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
        classtrib=classtrib_status,
        classtrib_freshness=(
            ClassTribFreshnessOut(
                status=_fresh.status,
                source_state=_fresh.source_state,
                bundled_version_date=_fresh.bundled_version_date,
                bundled_version_age_days=_fresh.bundled_version_age_days,
                sync_execution=_fresh.sync_execution,
                local_codes=_fresh.local_codes,
                remote_codes=_fresh.remote_codes,
                detail=_fresh.detail,
                codes_added=list(_fresh.added),
                codes_removed=list(_fresh.removed),
            )
            if _fresh
            else None
        ),
    )


@router.get(
    "/deep",
    response_model=DeepHealthResponse,
    summary="Deep readiness probe (alias Magalu Cloud)",
)
def deep_health() -> DeepHealthResponse:
    """Alias de /health/ready — convenção de monitoramento Magalu Cloud."""
    return readiness()
