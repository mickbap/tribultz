"""Interface do adapter Rumy → Handoff Event v1.1 (Round 4 §3 — F2 preparação).

F2 DEFINITIVO ESTÁ BLOQUEADO: o contrato real do webhook do Rumy (eventos,
payload, event_id, assinatura, retry) ainda não foi validado tecnicamente —
capacidade de webhook foi confirmada por Produto, o contrato não. Esta fatia
entrega somente a interface e a validação interna; a implementação concreta
nasce quando houver payload/documentação reais ("nada de construir ficção
muito bem testada — continua sendo ficção").

Regra permanente do adapter (Round 3 A2): traduzir SEM deformar o domínio.
`rumy.qualificado` é sinal externo → `handoff.requested`; NUNCA vira
qualificação comercial Tribultz (Round 4 §7).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any

from app.services.handoff.contract import HandoffEvent


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
