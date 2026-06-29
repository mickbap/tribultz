"""GA4 Measurement Protocol — envio de eventos server-side.

Usado para o evento de receita `purchase`, que não pode ser disparado no
navegador: o checkout ASAAS é hospedado (o usuário sai do site) e a confirmação
chega no webhook do backend. Enviar `purchase` daqui fecha o ROI real
(receita por canal/usuário).

No-op sem `GA4_MP_API_SECRET` (mesmo padrão do Sentry) — zero impacto em dev/CI.
O api_secret é criado em: GA4 → Admin → Fluxos de dados → Measurement Protocol.

Limitação conhecida: sem o client_id real do navegador (cookie _ga), o evento
não é "costurado" à sessão web do usuário. Usamos um client_id estável derivado
do user_id — suficiente para contabilizar receita; o stitching completo (capturar
o _ga no checkout) fica como follow-up.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_MP_URL = "https://www.google-analytics.com/mp/collect"


def send_purchase(
    *,
    client_id: str,
    transaction_id: str,
    value: float,
    plan: str,
    currency: str = "BRL",
    user_id: str | None = None,
) -> bool:
    """Envia um evento `purchase` ao GA4 via Measurement Protocol.

    Retorna True se o request foi enviado, False se foi no-op (sem secret) ou falhou.
    Nunca levanta — telemetria não pode quebrar o fluxo de pagamento.
    """
    if not settings.GA4_MP_API_SECRET or not settings.GA4_MEASUREMENT_ID:
        return False

    payload: dict = {
        "client_id": client_id,
        "events": [
            {
                "name": "purchase",
                "params": {
                    "transaction_id": transaction_id,
                    "value": value,
                    "currency": currency,
                    "items": [{"item_name": plan, "price": value, "quantity": 1}],
                },
            }
        ],
    }
    if user_id:
        payload["user_id"] = user_id

    try:
        resp = httpx.post(
            _MP_URL,
            params={
                "measurement_id": settings.GA4_MEASUREMENT_ID,
                "api_secret": settings.GA4_MP_API_SECRET,
            },
            json=payload,
            timeout=5.0,
        )
        # GA4 MP responde 2xx mesmo para payloads inválidos; logamos não-2xx.
        if resp.status_code >= 300:
            logger.warning("GA4 MP purchase status=%s body=%s", resp.status_code, resp.text[:200])
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — telemetria nunca quebra o webhook
        logger.warning("GA4 MP purchase falhou: %s", exc)
        return False
