"""Verificação de assinatura do webhook Rumy — contrato público (Round 16-F/G).

Esquema REAL do fornecedor, conforme documentação técnica pública relatada em
28/08/2026 (#689). Substitui o esquema provisório do Round 5, que assinava só o
corpo e comparava em hexdigest — incompatível: rejeitaria 100% do tráfego
legítimo com 401.

Contrato implementado:
  assinatura = Base64( HMAC-SHA256( secret, f"{timestamp}.{raw_body}" ) )
  janela      = |now - timestamp| <= 300s
  headers     = X-Rumy-Signature, X-Rumy-Timestamp

⚠️ SUPOSIÇÃO EXPLÍCITA — ``timestamp`` é lido como **epoch em segundos**. A
documentação repassada especifica a concatenação e a janela, mas não o formato
do carimbo. Epoch-segundos é a convenção dominante; se o fornecedor usar ISO-8601
ou milissegundos, o único ponto a mudar é ``_parse_timestamp``. Não inventamos
tolerância a múltiplos formatos: aceitar tudo esconde o dia em que o produtor
muda de formato.

Fail-closed em todas as bordas: secret ausente, header ausente, carimbo
ilegível ou fora da janela ⇒ rejeita. Nada é persistido antes desta função
passar.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-rumy-signature"
TIMESTAMP_HEADER = "x-rumy-timestamp"
EVENT_ID_HEADER = "x-rumy-event-id"
EVENT_TYPE_HEADER = "x-rumy-event-type"

#: Janela máxima documentada pelo fornecedor. Vale para os dois lados: carimbo
#: no futuro também é rejeitado (relógio adiantado não vira passe livre).
MAX_SKEW_SECONDS = 300


def _parse_timestamp(raw: str) -> Optional[datetime]:
    """Epoch em segundos → datetime UTC. Qualquer outra coisa ⇒ None (rejeita)."""
    try:
        return datetime.fromtimestamp(int((raw or "").strip()), tz=timezone.utc)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def signing_payload(timestamp_header: str, raw_body: bytes) -> bytes:
    """Material assinado: ``{timestamp}.{rawBody}`` — corpo BRUTO, nunca reserializado."""
    return timestamp_header.encode() + b"." + raw_body


def expected_signature(timestamp_header: str, raw_body: bytes, secret: str) -> str:
    """Assinatura esperada em Base64 (não hexdigest)."""
    mac = hmac.new(secret.encode(), signing_payload(timestamp_header, raw_body), hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()


def verify_signature(
    raw_body: bytes,
    signature_header: str,
    timestamp_header: str = "",
    now: Optional[datetime] = None,
) -> bool:
    """Autentica origem e frescor. Todas as recusas são silenciosas p/ o cliente (401)."""
    secret = settings.RUMY_WEBHOOK_SECRET
    if not secret:
        logger.warning("RUMY_WEBHOOK_SECRET não configurado — rejeitando webhook (fail-closed)")
        return False
    if not signature_header or not timestamp_header:
        logger.warning(
            "rumy_signature_rejected reason=header_ausente sig=%s ts=%s",
            bool(signature_header),
            bool(timestamp_header),
        )
        return False

    sent_at = _parse_timestamp(timestamp_header)
    if sent_at is None:
        logger.warning("rumy_signature_rejected reason=timestamp_ilegivel")
        return False

    skew = abs(((now or datetime.now(timezone.utc)) - sent_at).total_seconds())
    if skew > MAX_SKEW_SECONDS:
        # Replay: a assinatura pode ser válida: o carimbo é que expirou.
        logger.warning("rumy_signature_rejected reason=fora_da_janela skew=%.0fs", skew)
        return False

    return hmac.compare_digest(
        expected_signature(timestamp_header, raw_body, secret), signature_header
    )
