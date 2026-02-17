"""HubSpotTool – CRM integration (MVP). All calls gated by HUBSPOT_ENABLED."""

import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.hubapi.com"


# ── Guard ─────────────────────────────────────────────────────
def _enabled() -> bool:
    return settings.HUBSPOT_ENABLED and bool(settings.HUBSPOT_PRIVATE_APP_TOKEN)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.HUBSPOT_PRIVATE_APP_TOKEN}",
        "Content-Type": "application/json",
    }


def _noop(entity: str) -> dict:
    """Return a no-op result when HubSpot is disabled."""
    return {"hubspot": "disabled", "entity": entity, "action": "skipped"}


# ── 1. Upsert Contact ────────────────────────────────────────
def upsert_contact(
    email: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    properties: Optional[dict[str, Any]] = None,
) -> dict:
    """Create or update a HubSpot contact by email."""
    if not _enabled():
        return _noop("contact")

    props: dict[str, Any] = {"email": email}
    if first_name:
        props["firstname"] = first_name
    if last_name:
        props["lastname"] = last_name
    if properties:
        props.update(properties)

    payload = {
        "properties": props,
        "idProperty": "email",
    }

    try:
        resp = httpx.post(
            f"{BASE_URL}/crm/v3/objects/contacts",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
        if resp.status_code == 409:
            # Contact exists – update
            contact_id = resp.json().get("message", "").split("ID: ")[-1].strip()
            resp = httpx.patch(
                f"{BASE_URL}/crm/v3/objects/contacts/{contact_id}",
                headers=_headers(),
                json={"properties": props},
                timeout=15,
            )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("HubSpot upsert_contact failed: %s", exc)
        return {"error": str(exc)}


# ── 2. Upsert Company ────────────────────────────────────────
def upsert_company(
    name: str,
    domain: Optional[str] = None,
    properties: Optional[dict[str, Any]] = None,
) -> dict:
    """Create or update a HubSpot company by name."""
    if not _enabled():
        return _noop("company")

    props: dict[str, Any] = {"name": name}
    if domain:
        props["domain"] = domain
    if properties:
        props.update(properties)

    try:
        resp = httpx.post(
            f"{BASE_URL}/crm/v3/objects/companies",
            headers=_headers(),
            json={"properties": props},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("HubSpot upsert_company failed: %s", exc)
        return {"error": str(exc)}


# ── 3. Upsert Deal ───────────────────────────────────────────
def upsert_deal(
    deal_name: str,
    stage: str = "appointmentscheduled",
    amount: Optional[float] = None,
    properties: Optional[dict[str, Any]] = None,
) -> dict:
    """Create a HubSpot deal."""
    if not _enabled():
        return _noop("deal")

    props: dict[str, Any] = {"dealname": deal_name, "dealstage": stage}
    if amount is not None:
        props["amount"] = str(amount)
    if properties:
        props.update(properties)

    try:
        resp = httpx.post(
            f"{BASE_URL}/crm/v3/objects/deals",
            headers=_headers(),
            json={"properties": props},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("HubSpot upsert_deal failed: %s", exc)
        return {"error": str(exc)}


# ── 4. Log Note ───────────────────────────────────────────────
def log_note(
    object_type: str,
    object_id: str,
    body: str,
) -> dict:
    """Attach a note (engagement) to a HubSpot object."""
    if not _enabled():
        return _noop("note")

    payload = {
        "properties": {
            "hs_note_body": body,
            "hs_timestamp": str(int(__import__("time").time() * 1000)),
        },
        "associations": [
            {
                "to": {"id": object_id},
                "types": [
                    {
                        "associationCategory": "HUBSPOT_DEFINED",
                        "associationTypeId": (
                            202 if object_type == "contacts"
                            else 214 if object_type == "companies"
                            else 216
                        ),
                    }
                ],
            }
        ],
    }

    try:
        resp = httpx.post(
            f"{BASE_URL}/crm/v3/objects/notes",
            headers=_headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        logger.error("HubSpot log_note failed: %s", exc)
        return {"error": str(exc)}
