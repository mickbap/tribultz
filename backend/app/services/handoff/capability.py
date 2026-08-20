"""Capacidades de provedores externos — DEC-7 (Round 7 §4/§12).

Separação obrigatória, válida como princípio para TODA integração externa:

- ``UNKNOWN_CAPABILITY`` — não existe evidência suficiente para afirmar se o
  fornecedor suporta a capacidade (não perguntamos, ou não responderam).
- ``UNSUPPORTED`` — existe evidência suficiente de que o fornecedor NÃO
  oferece a capacidade.

**Silêncio do fornecedor nunca produz UNSUPPORTED** — silêncio é decisão
operacional de não depender da capacidade, não prova de incapacidade. "Não
tem" encerra o assunto; "não sabemos" convida a perguntar de novo — o dado
precisa preservar essa diferença para quem o ler daqui a seis meses.
"""

from __future__ import annotations

import enum


class ProviderCapability(str, enum.Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"


#: Estado vigente da capacidade de supressão do Rumy (Round 7 §12):
#: as P0-2/12/15 seguem sem resposta factual ⇒ UNKNOWN_CAPABILITY.
RUMY_SUPPRESSION_CAPABILITY = ProviderCapability.UNKNOWN_CAPABILITY
RUMY_SEND_OBSERVABILITY_CAPABILITY = ProviderCapability.UNKNOWN_CAPABILITY


def declare_capability(
    new_state: ProviderCapability, evidence_ref: str | None = None
) -> ProviderCapability:
    """Valida uma mudança de estado de capacidade.

    ``UNSUPPORTED`` exige referência de evidência (resposta do fornecedor,
    documentação, demonstração) — sem evidência, o máximo alcançável é
    ``UNKNOWN_CAPABILITY``. Guard estrutural da regra "silêncio ≠ prova".
    """
    if new_state == ProviderCapability.UNSUPPORTED and not (evidence_ref or "").strip():
        raise ValueError(
            "UNSUPPORTED exige evidência (silêncio do fornecedor nunca produz "
            "UNSUPPORTED — DEC-7)"
        )
    return new_state
