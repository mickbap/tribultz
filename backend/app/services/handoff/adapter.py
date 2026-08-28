"""Adapter Rumy → Handoff Event v1.1 (Round 4 §3; concretizado no Round 16-G).

O bloqueio declarado aqui — "o contrato real do webhook do Rumy ainda não foi
validado tecnicamente" — CAIU: a documentação técnica pública chegou em
28/08/2026 (#690). Evento público único ``lead.converted``, motivos
``meeting_ready`` / ``contact_shared`` / ``cta_positive``.

Não existe evento de ownership no contrato público. Portanto NENHUM motivo
produz HUMAN_OWNED: ``lead.converted`` é sinal do fornecedor, e assumir a
conversa é ato humano observável no domínio Tribultz. A máquina de estados já
exige ator humano em AUTOMATED→HUMAN_OWNED e essa trava não foi afrouxada.

Regra permanente do adapter (Round 3 A2): traduzir SEM deformar o domínio.
`rumy.qualificado` é sinal externo → `handoff.requested`; NUNCA vira
qualificação comercial Tribultz (Round 4 §7).
"""

from __future__ import annotations

import abc
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.handoff.contract import (
    CompanyIdentityPayload,
    HandoffEvent,
    HandoffReason,
    LastInteraction,
    MaybeStr,
    PersonIdentityPayload,
)

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _new_ulid(now_ms: Optional[int] = None) -> str:
    """ULID interno (26 chars Crockford): 10 de tempo + 16 de aleatoriedade.

    Identidade INTERNA do evento. A idempotência de negócio NÃO depende dela —
    ``compute_idempotency_key`` ancora em ``provider_event_id`` quando presente
    —, então gerar um ULID novo por evento é seguro e mantém o id do fornecedor
    intacto no campo que é dele.
    """
    ms = now_ms if now_ms is not None else int(time.time() * 1000)
    out = []
    for _ in range(10):
        ms, r = divmod(ms, 32)
        out.append(_CROCKFORD[r])
    head = "".join(reversed(out))
    rnd = int.from_bytes(os.urandom(10), "big")
    tail = []
    for _ in range(16):
        rnd, r = divmod(rnd, 32)
        tail.append(_CROCKFORD[r])
    return head + "".join(reversed(tail))


def _maybe(value: Any) -> MaybeStr:
    """Valor nullable do produtor → MaybeStr. ``None``/vazio ⇒ absent, nunca placeholder."""
    if value is None:
        return MaybeStr.absent()
    text = str(value).strip()
    return MaybeStr.known(text) if text else MaybeStr.absent()


@dataclass(frozen=True)
class UnmappedEvent:
    """Evento do provedor sem mapeamento — vai ao ledger como 'unmapped' (auditoria)."""

    event_type_raw: str
    raw: dict[str, Any]
    note: str = ""


class RumyAdapter(abc.ABC):
    """Contrato do adapter. Implementação concreta: aguarda payload real (F2)."""

    #: versão do mapeamento gravada no ledger (adapter_version)
    version: str = "unimplemented"

    @abc.abstractmethod
    def to_handoff_event(self, raw: dict[str, Any]) -> HandoffEvent | UnmappedEvent:
        """Converte payload bruto do Rumy no evento interno, sem fabricar campos.

        - campo desconhecido/ausente ⇒ MaybeStr.absent(), nunca placeholder;
        - IDs preservados byte a byte em provider_ids;
        - evento não reconhecido ⇒ UnmappedEvent (auditar, zero efeito).
        """


class InternalEnvelopeAdapter(RumyAdapter):
    """Adapter provisório do Round 5 — aceita SOMENTE o envelope interno v1.1.

    NÃO é o adapter do Rumy: nenhuma suposição sobre o payload real do
    fornecedor foi codificada aqui (Round 5 §5: payload hipotético não vira
    contrato). Ele valida dicts já no formato do HandoffEvent v1.1, o que
    permite exercitar o pipeline completo (endpoint→ledger→worker→domínio)
    com fixtures sintéticas. Quando o payload real chegar, o RumyAdapter
    definitivo substitui este na seleção de get_adapter().
    """

    version = "internal-envelope-0.1"

    def to_handoff_event(self, raw: dict[str, Any]) -> HandoffEvent | UnmappedEvent:
        if not isinstance(raw, dict):
            raise ValueError("payload não é um objeto JSON")
        event_type = raw.get("event_type")
        if event_type != "handoff.requested":
            return UnmappedEvent(
                event_type_raw=str(event_type),
                raw=raw,
                note="envelope interno: tipo não mapeado (zero efeito, só auditoria)",
            )
        return HandoffEvent(**raw)


#: Motivo do Rumy → razão interna. Mapeamento EXPLÍCITO: motivo desconhecido
#: não vira ``other`` em silêncio — vira UnmappedEvent, que é auditável.
REASON_MAP: dict[str, HandoffReason] = {
    "meeting_ready": "meeting_request",
    "cta_positive": "positive_reply",
    "contact_shared": "contact_shared",
}

#: Autor da entrada de conversa → tipo de interação. ``system`` é marcador do
#: próprio Rumy (ex.: conversa truncada) e NUNCA pode virar fala do lead.
_KIND_BY_AUTHOR = {"lead": "reply", "system": "system_marker"}


class RumyLeadConvertedAdapter(RumyAdapter):
    """Adapter do contrato público do Rumy — evento ``lead.converted`` (#690)."""

    version = "rumy-lead-converted-1.0"
    EVENT_TYPE = "lead.converted"

    def to_handoff_event(self, raw: dict[str, Any]) -> HandoffEvent | UnmappedEvent:
        if not isinstance(raw, dict):
            raise ValueError("payload não é um objeto JSON")

        event_type = raw.get("event_type")
        if event_type != self.EVENT_TYPE:
            return UnmappedEvent(
                event_type_raw=str(event_type),
                raw=raw,
                note="fora do contrato público do Rumy (zero efeito, só auditoria)",
            )

        data = raw.get("data") or {}
        reason_raw = str(data.get("reason") or "").strip()
        reason = REASON_MAP.get(reason_raw)
        if reason is None:
            # Motivo novo do fornecedor: auditar, não adivinhar.
            return UnmappedEvent(
                event_type_raw=f"{self.EVENT_TYPE}:{reason_raw or '(sem reason)'}",
                raw=raw,
                note="reason fora do contrato conhecido — não mapeado para não deformar o domínio",
            )

        lead = data.get("lead") or {}
        company = data.get("company")  # nullable por contrato

        return HandoffEvent(
            event_id=_new_ulid(),
            provider_event_id=str(raw["id"]) if raw.get("id") is not None else None,
            api_version=str(raw["api_version"]) if raw.get("api_version") is not None else None,
            occurred_at=self._occurred_at(raw),
            external_lead_id=str(lead.get("id") or "").strip(),
            person=PersonIdentityPayload(
                full_name=str(lead.get("name") or "").strip(),
                email=_maybe(lead.get("email")),
                linkedin_url=_maybe(lead.get("linkedin_url")),
            ),
            company=CompanyIdentityPayload(
                name=_maybe((company or {}).get("name")),
                cnpj=_maybe((company or {}).get("cnpj")),
                domain=_maybe((company or {}).get("domain")),
            ),
            campaign_id=(str(data["campaign"]["id"]) if isinstance(data.get("campaign"), dict)
                         and data["campaign"].get("id") is not None else None),
            reason=reason,
            last_interaction=self._last_interaction(data.get("conversation")),
        )

    @staticmethod
    def _occurred_at(raw: dict[str, Any]) -> datetime:
        """Carimbo do produtor; sem ele, o instante da adaptação (nunca inventar passado)."""
        value = raw.get("occurred_at") or raw.get("created_at")
        if value:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    @staticmethod
    def _last_interaction(conversation: Any) -> Optional[LastInteraction]:
        """Última entrada da conversa, com autoria preservada.

        A conversa é truncável e o Rumy marca o corte com ``from=system``. Esse
        marcador vira ``kind="system_marker"`` — jamais ``reply`` —, porque
        tratá-lo como fala do lead inventaria um interesse que não existiu.
        """
        if not isinstance(conversation, list) or not conversation:
            return None
        last = conversation[-1]
        if not isinstance(last, dict):
            return None
        author = str(last.get("from") or "").strip().lower()
        at = last.get("at") or last.get("timestamp")
        parsed_at = None
        if at:
            try:
                parsed_at = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            except ValueError:
                parsed_at = None
        return LastInteraction(
            channel="linkedin",  # Rumy é LinkedIn-only
            kind=_KIND_BY_AUTHOR.get(author, "outbound"),
            at=parsed_at,
            ref=str(last.get("id")) if last.get("id") is not None else None,
        )


def get_adapter() -> RumyAdapter:
    """Adapter vigente: o do contrato público do Rumy (#690)."""
    return RumyLeadConvertedAdapter()
