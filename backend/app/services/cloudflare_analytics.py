"""Tráfego do site via Cloudflare GraphQL Analytics API (zona já proxied, plano Free).

`uniques` é uma aproximação de borda sobre todo o tráfego HTTP da zona —
inclui bots/crawlers, não só visitantes humanos. O plano Free não expõe
filtro por bot-score no GraphQL (recurso pago de Bot Management).
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://api.cloudflare.com/client/v4/graphql"
TIMEOUT_SECONDS = 5.0

_QUERY = """
query ($zoneTag: string!, $date: string!) {
  viewer {
    zones(filter: {zoneTag: $zoneTag}) {
      httpRequests1dGroups(filter: {date: $date}, limit: 1) {
        uniq { uniques }
        sum { requests pageViews }
      }
    }
  }
}
"""


async def get_today_traffic() -> dict[str, Any] | None:
    """Retorna tráfego do dia (UTC) ou None se não configurado/indisponível.

    Nunca levanta exceção — degrada graciosamente pra não quebrar o dashboard.
    """
    if not settings.CLOUDFLARE_ANALYTICS_TOKEN:
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.post(
                GRAPHQL_URL,
                headers={"Authorization": f"Bearer {settings.CLOUDFLARE_ANALYTICS_TOKEN}"},
                json={
                    "query": _QUERY,
                    "variables": {"zoneTag": settings.CLOUDFLARE_ZONE_ID, "date": today},
                },
            )
            if resp.status_code != 200:
                logger.warning("cloudflare_analytics_http_error", extra={"status": resp.status_code})
                return None
            data = resp.json()
            if data.get("errors"):
                logger.warning("cloudflare_analytics_graphql_error", extra={"errors": data["errors"]})
                return None
            groups = (
                data.get("data", {})
                .get("viewer", {})
                .get("zones", [{}])[0]
                .get("httpRequests1dGroups", [])
            )
            if not groups:
                return {"date": today, "uniques": 0, "page_views": 0, "requests": 0}
            group = groups[0]
            return {
                "date": today,
                "uniques": group.get("uniq", {}).get("uniques", 0),
                "page_views": group.get("sum", {}).get("pageViews", 0),
                "requests": group.get("sum", {}).get("requests", 0),
            }
    except Exception as exc:
        logger.warning("cloudflare_analytics_unavailable", extra={"error": str(exc)})
        return None
