"""Handoff Event v1.1 — contrato interno do handoff (Rounds 2–4, PO-2026-07-CRM-001).

Modelo INTERNO do domínio, não uma afirmação sobre o payload real do Rumy
(Round 4 §3: o adapter definitivo aguarda payload/documentação reais). Campos
com risco de fabricação usam semântica explícita known/absent — ausência nunca
vira valor inventado (Round 1 D-1/D-3): string vazia é rejeitada na validação.

Identidade lógica do lead: (tenant, source_system, external_lead_id) — o tenant
não viaja no evento; é resolvido pelo ingestor (Round 4 §11).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

SCHEMA_VERSION = "1.1"

# ULID canônico (Crockford base32, 26 chars) — gerado no produtor do evento.
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

EventType = Literal["handoff.requested"]
HandoffReason = Literal["positive_reply", "meeting_request", "manual_flag", "other"]


class MaybeStr(BaseModel):
    """Campo com presença explícita: known exige valor não-vazio; absent proíbe valor."""

    status: Literal["known", "absent"]
    value: Optional[str] = None

    @model_validator(mode="after")
    def _coherent(self) -> "MaybeStr":
        if self.status == "known":
            if self.value is None or not self.value.strip():
                raise ValueError("status=known exige value não-vazio")
        elif self.value is not None:
            raise ValueError("status=absent proíbe value")
        return self

    @classmethod
    def known(cls, value: str) -> "MaybeStr":
        return cls(status="known", value=value)

    @classmethod
    def absent(cls) -> "MaybeStr":
        return cls(status="absent")

    @property
    def is_known(self) -> bool:
        return self.status == "known"


class PersonIdentityPayload(BaseModel):
    full_name: str
    email: MaybeStr = Field(default_factory=MaybeStr.absent)
    linkedin_url: MaybeStr = Field(default_factory=MaybeStr.absent)

    @field_validator("full_name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("full_name não pode ser vazio")
        return v.strip()


class CompanyIdentityPayload(BaseModel):
    name: MaybeStr = Field(default_factory=MaybeStr.absent)
    cnpj: MaybeStr = Field(default_factory=MaybeStr.absent)
    domain: MaybeStr = Field(default_factory=MaybeStr.absent)


class LastInteraction(BaseModel):
    channel: str  # ex.: "linkedin" (Rumy é LinkedIn-only)
    kind: str  # ex.: "reaction", "reply", "message"
    at: Optional[datetime] = None
    ref: Optional[str] = None


class HandoffEvent(BaseModel):
    """Evento de handoff normalizado — o que o domínio Tribultz consome."""

    schema_version: Literal["1.1"] = SCHEMA_VERSION
    event_id: str
    event_type: EventType = "handoff.requested"
    occurred_at: datetime
    producer: str = "rumy"
    source_system: str = "rumy"
    external_lead_id: str
    person: PersonIdentityPayload
    company: CompanyIdentityPayload
    campaign_id: Optional[str] = None
    source_id: Optional[str] = None
    reason: HandoffReason = "other"
    last_interaction: Optional[LastInteraction] = None
    owner: MaybeStr = Field(default_factory=MaybeStr.absent)  # SUGERIDO, nunca imposto

    @field_validator("event_id")
    @classmethod
    def _ulid(cls, v: str) -> str:
        if not _ULID_RE.match(v or ""):
            raise ValueError("event_id deve ser ULID (26 chars Crockford base32)")
        return v

    @field_validator("external_lead_id", "source_system", "producer")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("campo obrigatório não pode ser vazio")
        return v.strip()

    @field_validator("occurred_at")
    @classmethod
    def _tz_aware_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at deve ser timezone-aware (UTC)")
        return v.astimezone(timezone.utc)

    @property
    def has_identity_minimum(self) -> bool:
        """Mínimo do Round 2 D-2: nome + (e-mail OU LinkedIn) + nome da empresa.

        Sem o mínimo o evento vai à quarentena (fila de exceção humana) — nunca
        gera escrita parcial nem placeholder.
        """
        return bool(
            self.person.full_name
            and (self.person.email.is_known or self.person.linkedin_url.is_known)
            and self.company.name.is_known
        )
