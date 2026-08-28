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
#: ``contact_shared`` entrou no Round 16-G (#690): o Rumy emite esse motivo em
#: ``lead.converted`` e ele não tinha destino fiel — cairia em ``other``, que é
#: onde a informação morre. Caso real: Manuel Torres forneceu o e-mail em 20/08
#: exatamente nesse padrão.
HandoffReason = Literal[
    "positive_reply", "meeting_request", "contact_shared", "manual_flag", "other"
]

#: Origens onde a EMPRESA deixa de ser requisito absoluto de identidade mínima
#: — decisão de Produto de 28/08/2026 (#690). Restrita a contratos com
#: identidade externa confiável: o Rumy autentica o evento e carrega um
#: ``external_lead_id`` próprio, então nome + (e-mail OU LinkedIn) já identifica
#: sem fabricar nada. NÃO é flexibilização global: outras origens seguem
#: exigindo empresa, e enfraquecê-las em silêncio era o risco a evitar.
COMPANY_OPTIONAL_ORIGINS = frozenset({"rumy"})


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
    #: Identidade INTERNA do evento (ULID). Não é o id do fornecedor.
    event_id: str
    #: Identidade EXTERNA, preservada byte a byte como o produtor enviou
    #: (ex.: ``evt_<uuid>`` do Rumy). Nunca coagida ao formato interno: coagir
    #: destrói a chave que serve à idempotência e à auditoria (#690).
    provider_event_id: Optional[str] = None
    #: Versão do contrato declarada pelo produtor — proveniência, não lógica.
    api_version: Optional[str] = None
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
    def company_is_optional(self) -> bool:
        """Empresa deixa de ser requisito só onde há identidade externa confiável.

        Duas condições, ambas necessárias: origem na allowlist E
        ``external_lead_id`` presente. Origem sozinha não basta — sem o id
        externo não há identidade confiável a invocar.
        """
        return (
            self.source_system in COMPANY_OPTIONAL_ORIGINS
            and bool((self.external_lead_id or "").strip())
        )

    @property
    def has_identity_minimum(self) -> bool:
        """Mínimo de identidade, por origem.

        Base (todas as origens): nome + (e-mail OU LinkedIn).
        Empresa: exigida por padrão (Round 2 D-2); dispensada nas origens de
        ``COMPANY_OPTIONAL_ORIGINS`` — decisão de Produto de 28/08 para o
        ``lead.converted`` do Rumy, cujo contrato documenta ``company`` como
        nullable (#690).

        Sem o mínimo o evento vai à quarentena (fila de exceção humana) — nunca
        gera escrita parcial nem placeholder. Empresa ausente permanece
        ``absent()``: não é fabricada, não é enriquecida e não vira conflito.
        """
        base = bool(
            self.person.full_name
            and (self.person.email.is_known or self.person.linkedin_url.is_known)
        )
        if not base:
            return False
        return True if self.company_is_optional else self.company.name.is_known
