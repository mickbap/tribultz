"""Enrichment sync — Attio CRM.

PO-2026-07-CRM-001, fatia 5/12. Writes computed enrichment data (Tribultz
score, ranking, financial indicators, ...) onto an existing record via a
partial PATCH — no dedup/create here, this assumes the record already
exists (created by upsert_company()/upsert_person() in earlier fatias).

financial_indicators has no matching native Attio attribute type (Attio's
17 attribute types are text/number/checkbox/date/select/multi_select/
currency/rating/email/phone/url/person_reference/company_reference/... —
no arbitrary JSON/object type, per
docs.attio.com/rest-api/attribute-types/attribute-types), so it's
serialized as a JSON string into a text attribute. Revisit if a structured
breakdown per indicator is needed later.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)

# Slugs de atributo custom — mesma ressalva das fatias anteriores: convenção
# nossa, não confirmados contra um workspace Attio real.
_ATTRS = {
    "score": "score_tribultz",
    "ranking": "ranking",
    "score_reason": "score_reason",
    "analysis_date": "analysis_date",
    "last_updated_date": "last_updated_date",
    "rf_origin": "rf_origin",
    "financial_indicators": "financial_indicators",
    "segment": "segment",
    "cnae": "cnae",
}


def sync_enrichment(
    record_id: str,
    score: Optional[float] = None,
    ranking: Optional[int] = None,
    score_reason: Optional[str] = None,
    analysis_date: Optional[str] = None,
    last_updated_date: Optional[str] = None,
    rf_origin: Optional[str] = None,
    financial_indicators: Optional[dict[str, Any]] = None,
    segment: Optional[str] = None,
    cnae: Optional[str] = None,
    object_type: str = "companies",
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Write enrichment fields onto an existing record via partial PATCH.

    Only fields actually passed are sent — None means "don't touch this
    attribute", not "clear it" (so score=0 or an empty financial_indicators
    dict are still written). Raises ValueError if nothing was passed, since
    that's a caller bug — there'd be nothing to sync, without ever calling
    the API, consistent with the fail-fast validation in pipeline.py.
    """
    raw_fields = {
        "score": score,
        "ranking": ranking,
        "score_reason": score_reason,
        "analysis_date": analysis_date,
        "last_updated_date": last_updated_date,
        "rf_origin": rf_origin,
        "financial_indicators": financial_indicators,
        "segment": segment,
        "cnae": cnae,
    }
    values: dict[str, Any] = {}
    for field, value in raw_fields.items():
        if value is None:
            continue
        if field == "financial_indicators":
            values[_ATTRS[field]] = json.dumps(value, ensure_ascii=False)
        else:
            values[_ATTRS[field]] = value

    if not values:
        raise ValueError("sync_enrichment: nenhum campo informado — nada para sincronizar")

    if not is_enabled():
        return noop("enrichment")

    client = client or AttioClient()
    logger.info(
        "attio_enrichment_sync object=%s record_id=%s fields=%s",
        object_type, record_id, list(values),
    )
    return client.request(
        "PATCH",
        f"/objects/{object_type}/records/{record_id}",
        json={"data": {"values": values}},
    )
