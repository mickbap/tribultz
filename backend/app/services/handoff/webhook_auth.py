"""Verificação de assinatura do webhook Rumy — contrato público (#689, hardening #693).

Esquema real do fornecedor:
  assinatura = Base64( HMAC-SHA256( secret, f"{timestamp}.{raw_body}" ) )
  janela      = |now - timestamp| <= 300s
  headers     = X-Rumy-Signature, X-Rumy-Timestamp, X-Rumy-Event-Id

Princípio desta camada: **entrada malformada nunca vira exceção**. Toda borda
devolve ``False`` e o router traduz em 401. Um 500 na fronteira de autenticação
é pior que um 401: transforma lixo do atacante em erro do servidor, e erro do
servidor é sinal — para ele, não para nós.

⚠️ SUPOSIÇÃO EXPLÍCITA — ``timestamp`` é epoch em **segundos**. A documentação
repassada especifica a concatenação e a janela, não o formato. Isolado em
``_parse_timestamp``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-rumy-signature"
TIMESTAMP_HEADER = "x-rumy-timestamp"
EVENT_ID_HEADER = "x-rumy-event-id"
EVENT_TYPE_HEADER = "x-rumy-event-type"

#: Janela máxima documentada. Vale nos dois sentidos: carimbo no futuro também
#: é rejeitado — relógio adiantado não vira passe livre.
MAX_SKEW_SECONDS = 300

#: ``crm_lead_events.idempotency_key`` é String(128) e a chave é ``evt:<id>``.
#: 124 é o teto real do id externo. Validar ANTES de montar a chave evita que
#: um header hostil vire erro de banco (500) em vez de recusa (400).
#: NÃO truncar: truncar cria colisão silenciosa entre ids longos distintos.
MAX_PROVIDER_EVENT_ID = 124

#: Base64 de um SHA-256 tem 44 chars. A faixa é folgada de propósito — o alvo
#: é barrar o que não é base64, não adivinhar o comprimento exato do produtor.
_B64_RE = re.compile(r"^[A-Za-z0-9+/]{40,120}={0,2}$")
#: Epoch em segundos, só dígitos ASCII. ``int()`` do Python aceita ``1_756``
#: e dígitos de largura total ("１７５６"); nenhum dos dois é o contrato.
_EPOCH_RE = re.compile(r"^[0-9]{1,19}$")
#: Id externo: imprimível ASCII, sem CR/LF nem controle (barra log injection e
#: header smuggling antes de qualquer persistência).
_EVENT_ID_RE = re.compile(r"^[\x21-\x7E]{1,%d}$" % MAX_PROVIDER_EVENT_ID)


def _secret() -> str:
    """Secret utilizável, ou string vazia. Nunca calcula HMAC com chave vazia."""
    raw = getattr(settings, "RUMY_WEBHOOK_SECRET", None)
    return raw.strip() if isinstance(raw, str) else ""


def is_valid_event_id(value: str) -> bool:
    """Id externo aceitável para virar chave de idempotência."""
    return bool(_EVENT_ID_RE.match(value or ""))


def _parse_timestamp(raw: str) -> Optional[datetime]:
    """Epoch em segundos → datetime UTC. Qualquer outra forma ⇒ None."""
    value = (raw or "").strip()
    if not _EPOCH_RE.match(value):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def signing_payload(timestamp_header: str, raw_body: bytes) -> bytes:
    """Material assinado: ``{timestamp}.{rawBody}`` — corpo BRUTO, sem reserializar."""
    return timestamp_header.encode("utf-8", "surrogateescape") + b"." + raw_body


def expected_signature(timestamp_header: str, raw_body: bytes, secret: str) -> str:
    """Assinatura esperada, Base64 (não hexdigest)."""
    mac = hmac.new(
        secret.encode(), signing_payload(timestamp_header, raw_body), hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode()


def verify_signature(
    raw_body: bytes,
    signature_header: str,
    timestamp_header: str = "",
    now: Optional[datetime] = None,
) -> bool:
    """Autentica origem e frescor. Nunca levanta; nunca registra segredo."""
    secret = _secret()
    if not secret:
        # Fail-closed: sem secret utilizável não há o que autenticar.
        logger.warning("rumy_signature_rejected reason=secret_ausente")
        return False

    sig = (signature_header or "").strip()
    if not sig or not timestamp_header:
        logger.warning(
            "rumy_signature_rejected reason=header_ausente sig=%s ts=%s",
            bool(sig), bool(timestamp_header),
        )
        return False

    if not _B64_RE.match(sig):
        # Barra não-ASCII e lixo antes do compare_digest, que levanta TypeError
        # com str não-ASCII — e TypeError aqui viraria 500 no lugar de 401.
        logger.warning("rumy_signature_rejected reason=assinatura_malformada")
        return False

    sent_at = _parse_timestamp(timestamp_header)
    if sent_at is None:
        logger.warning("rumy_signature_rejected reason=timestamp_ilegivel")
        return False

    skew = abs(((now or datetime.now(timezone.utc)) - sent_at).total_seconds())
    if skew > MAX_SKEW_SECONDS:
        logger.warning("rumy_signature_rejected reason=fora_da_janela skew=%.0fs", skew)
        return False

    # Ambos ASCII garantidos: sig pelo regex, expected por ser base64.
    return hmac.compare_digest(
        expected_signature(timestamp_header, raw_body, secret).encode("ascii"),
        sig.encode("ascii"),
    )
