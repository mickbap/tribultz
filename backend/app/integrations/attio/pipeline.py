"""Commercial pipeline sync — Attio CRM.

PO-2026-07-CRM-001, fatia 4/12. Assumes the pipeline List and its "Lead
Source" attribute already exist in the Attio workspace — schema/workspace
provisioning is manual admin setup, not this module's job (same stance as
the custom attribute slugs in companies.py/people.py). This module only
moves records through stages that must already be configured as select
options on the list's status attribute.

Upsert shape from docs.attio.com/rest-api/endpoint-reference/entries/upsert-a-list-entry-by-parent:
PUT /v2/lists/{list}/entries with {"data": {"parent_record_id", "parent_object", "entry_values"}}.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.config import settings
from app.integrations.attio.client import AttioClient, is_enabled, noop

logger = logging.getLogger(__name__)

# PO seção 5 — nomes de estágio exatos, em ordem. Precisam bater com as
# opções já configuradas no atributo de status da list no workspace.
PIPELINE_STAGES = (
    "Lead identificado",
    "Empresa criada",
    "Contato identificado",
    "Primeiro contato",
    "Resposta recebida",
    "Discovery",
    "Diagnóstico",
    "Proposta enviada",
    "Negociação",
    "Fechado ganho",
    "Fechado perdido",
)

# PO seção 6 — propriedade obrigatória "Lead Source", valores fixos.
LEAD_SOURCES = (
    "Rumy",
    "LinkedIn",
    "Cold Email",
    "Site",
    "Indicação",
    "Manual",
    "Outro",
)

STAGE_ATTRIBUTE = "stage"
LEAD_SOURCE_ATTRIBUTE = "lead_source"


def add_to_pipeline(
    parent_record_id: str,
    parent_object: str,
    stage: Optional[str] = None,
    list_slug: Optional[str] = None,
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Create or move a record's entry in the commercial pipeline list.

    parent_object is whichever Attio object the record belongs to
    ("companies" or "people") — the pipeline can track either. stage
    defaults to settings.ATTIO_DEFAULT_STAGE when omitted; list_slug
    defaults to settings.ATTIO_DEFAULT_PIPELINE. Validates the stage name
    before doing anything else, even when Attio is disabled.
    """
    resolved_stage = stage or settings.ATTIO_DEFAULT_STAGE
    if resolved_stage not in PIPELINE_STAGES:
        raise ValueError(f"estágio inválido: {resolved_stage!r} — esperado um de {PIPELINE_STAGES}")

    if not is_enabled():
        return noop("pipeline_entry")

    client = client or AttioClient()
    list_id = list_slug or settings.ATTIO_DEFAULT_PIPELINE
    logger.info("attio_pipeline_move parent_object=%s stage=%s", parent_object, resolved_stage)
    return client.request(
        "PUT",
        f"/lists/{list_id}/entries",
        json={
            "data": {
                "parent_record_id": parent_record_id,
                "parent_object": parent_object,
                "entry_values": {STAGE_ATTRIBUTE: resolved_stage},
            }
        },
    )


def set_lead_source(
    record_id: str,
    source: str,
    object_type: str = "companies",
    client: Optional[AttioClient] = None,
) -> dict[str, Any]:
    """Write the required Lead Source property on a record.

    Validates against the PO's fixed value list before doing anything else,
    even when Attio is disabled.
    """
    if source not in LEAD_SOURCES:
        raise ValueError(f"lead source inválido: {source!r} — esperado um de {LEAD_SOURCES}")

    if not is_enabled():
        return noop("lead_source")

    client = client or AttioClient()
    logger.info("attio_lead_source_set object=%s source=%s", object_type, source)
    return client.request(
        "PATCH",
        f"/objects/{object_type}/records/{record_id}",
        json={"data": {"values": {LEAD_SOURCE_ATTRIBUTE: source}}},
    )
