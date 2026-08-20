"""Verificação de assinatura do webhook Rumy — F2 (Round 5).

Esquema PROVISÓRIO: HMAC-SHA256 do corpo bruto com RUMY_WEBHOOK_SECRET, header
``X-Rumy-Signature`` — o material público do fornecedor confirma "webhooks
assinados" mas não documenta o esquema (pergunta P0.6). Quando a resposta real
chegar, só esta função e o nome do header mudam; o resto do pipeline fica.

Fail-closed, mesmo padrão do webhook do Attio (webhooks.py): secret ausente ⇒
rejeita tudo.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-rumy-signature"


def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    if not settings.RUMY_WEBHOOK_SECRET:
        logger.warning("RUMY_WEBHOOK_SECRET não configurado — rejeitando webhook (fail-closed)")
        return False
    if not signature_header:
        return False
    expected = hmac.new(
        settings.RUMY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
