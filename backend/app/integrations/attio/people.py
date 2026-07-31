"""Person sync — Attio CRM.

PO-2026-07-CRM-001, fatia 3/12. Same style as companies.py: general-purpose,
not coupled to any local model. Dedup by email before create — email is the
natural identity for a person, unlike companies there's no multi-field
cascade to design here.

The "company" attribute is a record-reference; written via Attio's domain
shorthand (a record-reference to a company can be set by passing its domain
string instead of looking up its record_id first — see
docs.attio.com/rest-api/attribute-types/attribute-types-record-reference).
The company must already exist in Attio for the link to resolve — callers
should upsert_company() first (see companies.py) when linking is needed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)

OBJECT = "people"

# email_addresses and name ship on Attio's default "people" object. job_title,
# linkedin and phone are workspace custom attributes in our assumption — same
# caveat as companies.py: no real workspace to confirm slugs against yet.
_CUSTOM_ATTRS = {
    "job_title": "job_title",
    "linkedin": "linkedin",
    "phone": "phone_numbers",
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
    email: str,
    first_name: Optional[str],
    last_name: Optional[str],
    job_title: Optional[str],
    linkedin: Optional[str],
    phone: Optional[str],
    company_domain: Optional[str],
) -> dict[str, Any]:
    values: dict[str, Any] = {"email_addresses": [email]}
    if first_name or last_name:
        values["name"] = {"first_name": first_name or "", "last_name": last_name or ""}
    if company_domain:
        values["company"] = [company_domain]
    optional_fields = {"job_title": job_title, "linkedin": linkedin, "phone": phone}
    for field, value in optional_fields.items():
        if value:
            values[_CUSTOM_ATTRS[field]] = value
    return values


def upsert_person(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    job_title: Optional[str] = None,
    linkedin: Optional[str] = None,
    phone: Optional[str] = None,
    company_domain: Optional[str] = None,
    attio_person_id: Optional[str] = None,
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Create or update a person in Attio, deduplicating by email before create.

    Search order: attio_person_id (caller already knows it — skips search) →
    email. Falls back to creating a new record matched on email when nothing
    is found. Pass company_domain to link the person to an existing company
    (see module docstring — the company must already exist).
    """
    if not is_enabled():
        return noop("person")

    client = client or AttioClient()
    values = _values_payload(email, first_name, last_name, job_title, linkedin, phone, company_domain)

    record_id = attio_person_id or _find_record_id(client, "email_addresses", email)

    if record_id:
        logger.info("attio_person_update record_id=%s", record_id)
        return client.request(
            "PATCH",
            f"/objects/{OBJECT}/records/{record_id}",
            json={"data": {"values": values}},
        )

    logger.info("attio_person_create matching_attribute=email_addresses")
    return client.request(
        "PUT",
        f"/objects/{OBJECT}/records",
        params={"matching_attribute": "email_addresses"},
        json={"data": {"values": values}},
    )
