"""Webhook signature verification — Attio CRM.

PO-2026-07-CRM-001, fatia 7/12. Attio signs every webhook request with
HMAC-SHA256 of the raw request body using the shared secret, sent in the
"Attio-Signature" header (duplicated as "X-Attio-Signature" for legacy
clients — docs.attio.com/rest-api/guides/webhooks). Same verification
pattern already used in this codebase for Asaas
(app/services/asaas_service.py:verify_webhook_token).
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def verify_signature(raw_body: bytes, signature_header: str) -> bool:
    """Verify an inbound Attio webhook's HMAC-SHA256 signature.

    Rejects (returns False) when ATTIO_WEBHOOK_SECRET isn't configured or
    the header is empty — same fail-closed stance as Asaas's webhook check.
    """
    if not settings.ATTIO_WEBHOOK_SECRET:
        logger.warning("ATTIO_WEBHOOK_SECRET not configured, rejecting webhook")
        return False
    if not signature_header:
        return False

    expected = hmac.new(
        settings.ATTIO_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)
