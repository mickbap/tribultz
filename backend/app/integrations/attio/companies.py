"""Company sync — Attio CRM.

PO-2026-07-CRM-001, fatia 2/12. Cascading dedup before create: caller-supplied
Attio record id → CNPJ → domain. General-purpose module (mirrors
app/tools/hubspot_tool.py's style) — not coupled to prospect_org; wiring this
into the prospecting pipeline is a separate decision, not part of this fatia.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)

OBJECT = "companies"

# Attio's default "companies" object ships with `name` and `domains` out of
# the box; everything else below is a workspace custom attribute. Slugs are
# our naming convention (snake_case) — custom attribute slugs are configured
# per workspace and can't be verified without one, so confirm these against
# the real Attio workspace schema before relying on them in production.
_CUSTOM_ATTRS = {
    "cnpj": "cnpj",
    "razao_social": "razao_social",
    "nome_fantasia": "nome_fantasia",
    "cidade": "cidade",
    "estado": "estado",
    "cnae_principal": "cnae_principal",
    "porte": "porte",
    "situacao_cadastral": "situacao_cadastral",
    "website": "website",
}


def _find_record_id(client: AttioClient, attribute: str, value: str) -> Optional[str]:
    result = client.request(
        "POST",
        f"/objects/{OBJECT}/records/query",
        json={"filter": {attribute: {"$eq": value}}, "limit": 1},
    )
    records = result.get("records", [])
    return records[0]["id"]["record_id"] if records else None


def _values_payload(
    name: str,
    cnpj: Optional[str],
    domain: Optional[str],
    razao_social: Optional[str],
    nome_fantasia: Optional[str],
    cidade: Optional[str],
    estado: Optional[str],
    cnae_principal: Optional[str],
    porte: Optional[str],
    situacao_cadastral: Optional[str],
    website: Optional[str],
) -> dict[str, Any]:
    values: dict[str, Any] = {"name": name}
    if domain:
        values["domains"] = [domain]
    optional_fields = {
        "cnpj": cnpj,
        "razao_social": razao_social,
        "nome_fantasia": nome_fantasia,
        "cidade": cidade,
        "estado": estado,
        "cnae_principal": cnae_principal,
        "porte": porte,
        "situacao_cadastral": situacao_cadastral,
        "website": website,
    }
    for field, value in optional_fields.items():
        if value:
            values[_CUSTOM_ATTRS[field]] = value
    return values


def upsert_company(
    name: str,
    cnpj: Optional[str] = None,
    domain: Optional[str] = None,
    razao_social: Optional[str] = None,
    nome_fantasia: Optional[str] = None,
    cidade: Optional[str] = None,
    estado: Optional[str] = None,
    cnae_principal: Optional[str] = None,
    porte: Optional[str] = None,
    situacao_cadastral: Optional[str] = None,
    website: Optional[str] = None,
    attio_company_id: Optional[str] = None,
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Create or update a company in Attio, deduplicating before create.

    Search order: attio_company_id (caller already knows it — skips search
    entirely) → CNPJ → domain. Falls back to creating a new record when
    nothing is found, matched on the strongest identifier available (CNPJ >
    domain > name) so a retried create can't silently duplicate.
    """
    if not is_enabled():
        return noop("company")

    client = client or AttioClient()
    values = _values_payload(
        name, cnpj, domain, razao_social, nome_fantasia, cidade, estado,
        cnae_principal, porte, situacao_cadastral, website,
    )

    record_id = attio_company_id
    if not record_id and cnpj:
        record_id = _find_record_id(client, _CUSTOM_ATTRS["cnpj"], cnpj)
    if not record_id and domain:
        record_id = _find_record_id(client, "domains", domain)

    if record_id:
        logger.info("attio_company_update record_id=%s", record_id)
        return client.request(
            "PATCH",
            f"/objects/{OBJECT}/records/{record_id}",
            json={"data": {"values": values}},
        )

    if cnpj:
        matching_attribute = _CUSTOM_ATTRS["cnpj"]
    elif domain:
        matching_attribute = "domains"
    else:
        matching_attribute = "name"

    logger.info("attio_company_create matching_attribute=%s", matching_attribute)
    return client.request(
        "PUT",
        f"/objects/{OBJECT}/records",
        params={"matching_attribute": matching_attribute},
        json={"data": {"values": values}},
    )
