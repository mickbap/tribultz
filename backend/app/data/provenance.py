"""Identidade auditável de artefato regulatório (#682) — fundação genérica.

Antes disto, a identidade dos artefatos que o motor implementa era uma única
constante em ``rulesMeta.ts`` (``NT_CURRENT_VERSION``): duas entradas, só o
número da versão, mantidas à mão. Não respondia contra QUAL artefato uma regra
foi escrita, QUANDO observamos aquela versão como vigente, nem se o conteúdo
mudou desde então.

O precedente parcial era ``classtrib_source.py``: tem ``source_url``,
``extraction_method``, ``date`` e ``data_signature()``. Faltavam ``artefato`` e
``versao`` — a tabela SVRS é página viva, sem versão declarada, e por isso esses
dois campos nunca precisaram existir lá. Este módulo generaliza o padrão sem
duplicá-lo: fontes vivas continuam expressáveis, com ``versao=None``.

Contrato mínimo (por artefato):

    artefato | versao | fonte | source_url | observado_em | fingerprint

Fronteira DELIBERADA: este módulo cuida de IDENTIDADE, não de conteúdo. Ele não
sabe o que a NT diz, não interpreta regra e não decide cobertura. Saber "qual
documento, em que versão, observado quando, com que conteúdo" é pré-requisito
para auditar uma decisão fiscal — não é a decisão.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass, replace
from typing import Any, Optional
from urllib.parse import urlparse

#: Hosts aceitos como AUTORIDADE NORMATIVA.
#:
#: Fonte secundária (fórum, blog, documentação de fornecedor, agregador) pode no
#: máximo ajudar a LOCALIZAR um documento; o conteúdo incorporado ao produto tem
#: de ser rastreável ao portal oficial. Esta allowlist é o ponto onde essa regra
#: deixa de ser combinado e vira mecanismo: registrar proveniência apontando para
#: outro host levanta ``ProvenanceError``.
OFFICIAL_HOSTS: frozenset[str] = frozenset({
    "www.nfe.fazenda.gov.br",
    "nfe.fazenda.gov.br",
    "dfe-portal.svrs.rs.gov.br",
    "www.svrs.rs.gov.br",
    "www.gov.br",
    "www.confaz.fazenda.gov.br",
    "www.planalto.gov.br",
})


class ProvenanceError(ValueError):
    """Proveniência inválida — nunca degrada em aviso."""


def fingerprint_bytes(raw: bytes) -> str:
    """SHA-256 do conteúdo BRUTO, como veio da fonte oficial.

    Bruto de propósito: qualquer normalização nossa (parse, encoding, ordenação)
    é interpretação, e interpretação não pode entrar na identidade do artefato.
    """
    return hashlib.sha256(raw).hexdigest()


def fingerprint_payload(payload: Any) -> str:
    """SHA-256 de uma estrutura já normalizada, para fonte viva sem arquivo.

    Serve ao caso da tabela SVRS, extraída de HTML: não existe "arquivo oficial"
    para hashear, então o hash cobre o conteúdo normalizado. Continua detectando
    edição in-place, que é o que importa.
    """
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ArtifactProvenance:
    """Identidade de um artefato regulatório observado numa data.

    ``versao=None`` é estado legítimo, não ausência de dado: descreve fonte viva
    que não declara versão (ex.: consulta pública SVRS). Distinguir "não tem
    versão" de "não sabemos a versão" importa — o segundo caso deve falhar, e
    falha, porque ``versao`` vazia (string em branco) é rejeitada.
    """

    artefato: str
    versao: Optional[str]
    fonte: str
    source_url: str
    observado_em: dt.date
    fingerprint: str
    notas: str = ""

    def __post_init__(self) -> None:
        if not self.artefato.strip():
            raise ProvenanceError("artefato é obrigatório")
        if self.versao is not None and not self.versao.strip():
            raise ProvenanceError(
                "versao vazia é ambígua: use None para fonte viva sem versão declarada"
            )
        if not self.fonte.strip():
            raise ProvenanceError("fonte é obrigatória")
        if not self.fingerprint.strip():
            raise ProvenanceError("fingerprint é obrigatório")
        host = (urlparse(self.source_url).hostname or "").lower()
        if host not in OFFICIAL_HOSTS:
            raise ProvenanceError(
                f"source_url aponta para host não oficial: {host!r}. "
                "Fonte secundária pode localizar o documento, nunca ser a autoridade."
            )

    @property
    def is_live_source(self) -> bool:
        """Fonte viva = artefato sem versão declarada pela própria fonte."""
        return self.versao is None

    def rotulo(self) -> str:
        return f"{self.artefato} v{self.versao}" if self.versao else f"{self.artefato} (fonte viva)"

    def changed_from(self, outro: "ArtifactProvenance") -> bool:
        """Mudou o conteúdo? Compara fingerprint, jamais data de observação.

        Reobservar o mesmo artefato num dia diferente NÃO é mudança — é o caso
        normal do sync diário. Só o conteúdo conta.
        """
        return self.fingerprint != outro.fingerprint

    def observed_now(self, quando: dt.date) -> "ArtifactProvenance":
        return replace(self, observado_em=quando)

    def to_dict(self) -> dict:
        return {
            "artefato": self.artefato,
            "versao": self.versao,
            "fonte": self.fonte,
            "source_url": self.source_url,
            "observado_em": self.observado_em.isoformat(),
            "fingerprint": self.fingerprint,
            "notas": self.notas,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ArtifactProvenance":
        return cls(
            artefato=d["artefato"],
            versao=d.get("versao"),
            fonte=d["fonte"],
            source_url=d["source_url"],
            observado_em=dt.date.fromisoformat(d["observado_em"]),
            fingerprint=d["fingerprint"],
            notas=d.get("notas", ""),
        )
