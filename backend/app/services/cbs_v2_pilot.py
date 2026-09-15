"""Infraestrutura fail-closed do piloto das APIs de apuração CBS v2.

Nenhuma função deste módulo compara o observado com o motor fiscal. O payload
externo é evidência, nunca uma mutação do resultado independente do Tribultz.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models.cbs_v2_pilot import (
    CbsV2ExternalObservation,
    CbsV2SyncRun,
    CbsV2SyncRunEvent,
)
from app.tools.s3_tool import put_immutable_object

CONTRACT_VERSION = "CBS_APURACAO_V2_DOC_1.0_2026-09-03"
PARSER_VERSION = "CBS_V2_TOLERANT_1"
ENVIRONMENTS = frozenset({"PRODUCAO_RESTRITA", "BETA"})
RESOURCES = frozenset({"DEBITOS", "CREDITOS"})
STATES = frozenset({"PENDENTE", "EM_PROCESSAMENTO", "CONCLUIDA", "ERRO"})
KNOWN_TOP_LEVEL_FIELDS = frozenset(
    {
        "tiqueteSolicitacao",
        "ticket",
        "estado",
        "situacao",
        "tempoEstimadoSegundos",
        "urlRetorno",
        "urlAssinada",
        "urlAssinadaExpiraEm",
        "dataExpiracao",
        "codigoErro",
        "mensagemErro",
    }
)


class PilotDisabledError(RuntimeError):
    pass


class SyncRunNotFoundError(LookupError):
    pass


class TicketFingerprintConflictError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedSyncRun:
    run: CbsV2SyncRun
    request_body: bytes
    callback_url: str


@dataclass(frozen=True)
class ParsedPayload:
    sanitized_payload: dict[str, Any]
    unknown_fields: list[str]
    schema_status: str
    ticket: str | None
    state: str
    signed_url_expires_at: datetime | None


@dataclass(frozen=True)
class IngestedObservation:
    event: CbsV2SyncRunEvent
    observation: CbsV2ExternalObservation
    created: bool


def pilot_activation_gates() -> dict[str, bool]:
    """Estado dos quatro gates operacionais definidos para o piloto."""
    return {
        "API_V2_DISPONIVEL": bool(
            settings.CBS_V2_API_AVAILABLE and settings.CBS_V2_API_BASE_URL.strip()
        ),
        "CREDENCIAL_PILOTO": bool(
            settings.CBS_V2_CLIENT_ID.strip() and settings.CBS_V2_CLIENT_SECRET.strip()
        ),
        "PAYLOAD_REAL_OBSERVADO": bool(settings.CBS_V2_REAL_PAYLOAD_OBSERVED),
        "FEATURE_FLAG_EXPLICITA": bool(settings.CBS_V2_PILOT_ENABLED),
    }


def pilot_is_active() -> bool:
    return all(pilot_activation_gates().values())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def prepare_sync_run(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    environment: str,
    resource: str,
    cnpj_base: str,
    callback_base_url: str,
    requested_at: datetime | None = None,
) -> PreparedSyncRun:
    """Cria o envelope imutável; não realiza POST para a RFB."""
    environment = environment.strip().upper()
    resource = resource.strip().upper()
    if environment not in ENVIRONMENTS:
        raise ValueError("ambiente CBS v2 inválido")
    if resource not in RESOURCES:
        raise ValueError("recurso CBS v2 inválido")
    if not re.fullmatch(r"\d{8}", cnpj_base):
        raise ValueError("CNPJ-base deve conter exatamente 8 dígitos")
    if not callback_base_url.startswith("https://"):
        raise ValueError("callback do piloto deve usar HTTPS")

    callback_id = uuid.uuid4()
    callback_url = f"{callback_base_url.rstrip('/')}/{callback_id}"
    request_body = _canonical_json({"urlRetorno": callback_url})
    run = CbsV2SyncRun(
        tenant_id=tenant_id,
        callback_id=callback_id,
        contract_version=CONTRACT_VERSION,
        environment=environment,
        resource=resource,
        cnpj_base=cnpj_base,
        request_fingerprint=_sha256(request_body),
        requested_at=requested_at or datetime.now(timezone.utc),
    )
    session.add(run)
    session.flush()
    return PreparedSyncRun(run=run, request_body=request_body, callback_url=callback_url)


def get_sync_run_for_tenant(
    session: Session, *, tenant_id: uuid.UUID, sync_run_id: uuid.UUID
) -> CbsV2SyncRun | None:
    return session.scalar(
        select(CbsV2SyncRun).where(
            CbsV2SyncRun.id == sync_run_id,
            CbsV2SyncRun.tenant_id == tenant_id,
        )
    )


def get_sync_run_by_callback(
    session: Session, *, callback_id: uuid.UUID
) -> CbsV2SyncRun | None:
    # Tenant nunca vem do corpo externo: é resolvido pela referência opaca.
    return session.scalar(
        select(CbsV2SyncRun).where(CbsV2SyncRun.callback_id == callback_id)
    )


def _redact_urls(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED_URL]" if "url" in str(key).lower() else _redact_urls(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_urls(item) for item in value]
    return value


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_external_payload(raw_body: bytes) -> ParsedPayload:
    """Parse tolerante: desconhecido é preservado e torna o dado incomparável."""
    try:
        decoded = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ParsedPayload(
            sanitized_payload={"_raw_preserved": True, "_json_decodable": False},
            unknown_fields=[],
            schema_status="NON_JSON",
            ticket=None,
            state="INDETERMINADO",
            signed_url_expires_at=None,
        )
    if not isinstance(decoded, dict):
        return ParsedPayload(
            sanitized_payload={"_raw_preserved": True, "_json_root_type": type(decoded).__name__},
            unknown_fields=[],
            schema_status="INCOMPATIBLE",
            ticket=None,
            state="INDETERMINADO",
            signed_url_expires_at=None,
        )

    unknown = sorted(str(key) for key in decoded if key not in KNOWN_TOP_LEVEL_FIELDS)
    ticket_value = decoded.get("tiqueteSolicitacao", decoded.get("ticket"))
    ticket = str(ticket_value).strip() if ticket_value is not None else None
    if ticket == "" or (ticket is not None and len(ticket) > 160):
        ticket = None
    raw_state = str(decoded.get("situacao", decoded.get("estado", ""))).strip().upper()
    state = raw_state if raw_state in STATES else "INDETERMINADO"
    if state == "INDETERMINADO" and ticket and not raw_state:
        state = "REQUEST_ACCEPTED"
    expires = _parse_datetime(
        decoded.get("urlAssinadaExpiraEm", decoded.get("dataExpiracao"))
    )
    return ParsedPayload(
        sanitized_payload=_redact_urls(decoded),
        unknown_fields=unknown,
        schema_status="UNKNOWN_FIELDS" if unknown else "KNOWN_SUBSET",
        ticket=ticket,
        state=state,
        signed_url_expires_at=expires,
    )


def _existing_ingest(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    dedupe_key: str,
) -> IngestedObservation | None:
    event = session.scalar(
        select(CbsV2SyncRunEvent).where(
            CbsV2SyncRunEvent.tenant_id == tenant_id,
            CbsV2SyncRunEvent.dedupe_key == dedupe_key,
        )
    )
    if event is None:
        return None
    if event.sync_run_id != sync_run_id:
        raise TicketFingerprintConflictError(
            "ticket e fingerprint já pertencem a outra sync run"
        )
    observation = session.scalar(
        select(CbsV2ExternalObservation).where(
            CbsV2ExternalObservation.sync_run_event_id == event.id,
            CbsV2ExternalObservation.tenant_id == tenant_id,
        )
    )
    if observation is None:
        raise RuntimeError("evento CBS v2 sem observação correspondente")
    return IngestedObservation(event=event, observation=observation, created=False)


def ingest_external_payload(
    session: Session,
    *,
    run: CbsV2SyncRun,
    raw_body: bytes,
    source: str,
    content_type: str = "application/json",
    observed_at: datetime | None = None,
    synthetic_fixture: bool = False,
    ticket_hint: str | None = None,
    transport_status_code: int | None = None,
) -> IngestedObservation:
    """Persiste bruto e acrescenta observação sem alterar fatos anteriores."""
    if source not in {"WEBHOOK", "STATUS_POLL", "REQUEST_RESPONSE", "DOWNLOAD_ARTIFACT"}:
        raise ValueError("fonte de observação inválida")
    if transport_status_code is not None and not 100 <= transport_status_code <= 599:
        raise ValueError("status de transporte inválido")
    fingerprint = _sha256(raw_body)
    parsed = parse_external_payload(raw_body)
    normalized_hint = ticket_hint.strip() if ticket_hint else None
    if normalized_hint is not None and len(normalized_hint) > 160:
        raise ValueError("ticket hint inválido")
    if parsed.ticket and normalized_hint and parsed.ticket != normalized_hint:
        raise TicketFingerprintConflictError("ticket do payload diverge do ticket esperado")
    effective_ticket = parsed.ticket or normalized_hint
    ticket_component = effective_ticket or f"SEM_TICKET:{run.id}"
    dedupe_key = _sha256(f"{ticket_component}\0{fingerprint}".encode())
    existing = _existing_ingest(
        session,
        tenant_id=run.tenant_id,
        sync_run_id=run.id,
        dedupe_key=dedupe_key,
    )
    if existing:
        return existing

    object_key = f"cbs-v2-pilot/{run.tenant_id}/{run.id}/{fingerprint}.raw"
    stored = put_immutable_object(
        key=object_key,
        data=raw_body,
        content_type=content_type,
        metadata={
            "classification": "external-evidence",
            "contract-version": run.contract_version,
        },
    )
    timestamp = observed_at or datetime.now(timezone.utc)

    # Lock lineariza a cadeia de eventos sem modificar o envelope imutável.
    session.scalar(select(CbsV2SyncRun.id).where(CbsV2SyncRun.id == run.id).with_for_update())
    previous = session.scalar(
        select(CbsV2SyncRunEvent)
        .where(CbsV2SyncRunEvent.sync_run_id == run.id)
        .order_by(CbsV2SyncRunEvent.created_at.desc(), CbsV2SyncRunEvent.id.desc())
        .limit(1)
    )
    event = CbsV2SyncRunEvent(
        sync_run_id=run.id,
        tenant_id=run.tenant_id,
        previous_event_id=previous.id if previous else None,
        source=source,
        state=parsed.state,
        ticket=effective_ticket,
        observed_at=timestamp,
        response_fingerprint=fingerprint,
        artifact_fingerprint=stored["checksum_sha256"],
        dedupe_key=dedupe_key,
        signed_url_expires_at=parsed.signed_url_expires_at,
        transport_status_code=transport_status_code,
        result="NOT_COMPARABLE" if parsed.schema_status == "KNOWN_SUBSET" else "INDETERMINADO",
    )
    observation = CbsV2ExternalObservation(
        tenant_id=run.tenant_id,
        sync_run_id=run.id,
        sync_run_event_id=event.id,
        previous_observation_id=None,
        external_transaction_id=None,
        observation_version=1,
        observed_at=timestamp,
        contract_version=run.contract_version,
        parser_version=PARSER_VERSION,
        resource=run.resource,
        source_payload_fingerprint=fingerprint,
        raw_bucket=stored["bucket"],
        raw_object_key=stored["key"],
        raw_size_bytes=stored["size_bytes"],
        raw_content_type=content_type[:160],
        sanitized_payload=parsed.sanitized_payload,
        unknown_fields=parsed.unknown_fields,
        schema_status=parsed.schema_status,
        comparability="NOT_COMPARABLE",
        determination="INDETERMINADO",
        synthetic_fixture=synthetic_fixture,
    )

    savepoint = session.begin_nested()
    try:
        session.add(event)
        session.flush()
        observation.sync_run_event_id = event.id
        session.add(observation)
        session.flush()
        savepoint.commit()
    except IntegrityError:
        savepoint.rollback()
        concurrent = _existing_ingest(
            session,
            tenant_id=run.tenant_id,
            sync_run_id=run.id,
            dedupe_key=dedupe_key,
        )
        if concurrent is None:
            raise
        return concurrent
    return IngestedObservation(event=event, observation=observation, created=True)


def latest_ticket_for_run(session: Session, *, run: CbsV2SyncRun) -> str | None:
    return session.scalar(
        select(CbsV2SyncRunEvent.ticket)
        .where(
            CbsV2SyncRunEvent.sync_run_id == run.id,
            CbsV2SyncRunEvent.tenant_id == run.tenant_id,
            CbsV2SyncRunEvent.ticket.is_not(None),
        )
        .order_by(CbsV2SyncRunEvent.created_at.desc())
        .limit(1)
    )


def recover_ticket_status(
    session: Session,
    *,
    tenant_id: uuid.UUID,
    sync_run_id: uuid.UUID,
    access_token: str,
    client: httpx.Client | None = None,
) -> IngestedObservation:
    """Consulta manual de recuperação; não agenda nem interpreta checkpoint."""
    if not pilot_is_active():
        raise PilotDisabledError("piloto CBS v2 não habilitado pelos quatro gates")
    run = get_sync_run_for_tenant(session, tenant_id=tenant_id, sync_run_id=sync_run_id)
    if run is None:
        raise SyncRunNotFoundError("sync run não encontrado para o tenant")
    ticket = latest_ticket_for_run(session, run=run)
    if not ticket:
        raise ValueError("sync run ainda não possui ticket observado")
    if not access_token.strip():
        raise ValueError("access token efêmero ausente")

    prefix = "/apuracao-cbs-prr/v2" if run.environment == "PRODUCAO_RESTRITA" else "/apuracao-cbs/v2"
    url = f"{settings.CBS_V2_API_BASE_URL.rstrip('/')}{prefix}/situacao/{quote(ticket, safe='')}"
    owns_client = client is None
    http_client = client or httpx.Client(timeout=30.0)
    try:
        response = http_client.get(
            url,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        ingested = ingest_external_payload(
            session,
            run=run,
            raw_body=response.content,
            source="STATUS_POLL",
            content_type=response.headers.get("content-type", "application/octet-stream"),
            transport_status_code=response.status_code,
        )
        return ingested
    finally:
        if owns_client:
            http_client.close()
