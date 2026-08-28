"""Reconciliação Attio ↔ domínio por ``external_lead_id`` — Fatia 1 (#691).

Por que existe: cinco leads reais foram materializados **manualmente** no Attio
em 23/08. Nenhum código os produziu e nenhum vínculo de volta foi estabelecido —
``crm_lead_links.attio_person_id`` está NULL para todos. As duas pontas existem
e não se conhecem. Qualquer projeção executada nesse estado criaria duplicatas.

O que esta camada faz: **liga as pontas**. Só isso.

Fronteiras, todas deliberadas:
  - **não** cria pessoa, empresa ou entrada de lista no Attio;
  - **não** toca fase, ownership, histórico ou qualquer eixo comercial;
  - **não** resolve ambiguidade por heurística — divergência é relatada, não
    adivinhada (fail-closed). Escolher em silêncio é pior que não escolher: o
    erro fica plausível e ninguém revisa.

``dry_run=True`` é o padrão. Escrever exige pedido explícito.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.crm_handoff import CrmLeadLink

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttioEntry:
    """Uma entrada da lista do Attio, como lida — sem interpretação."""

    external_lead_id: str
    person_id: str
    company_id: Optional[str] = None


@dataclass
class ReconciliationReport:
    """Resultado auditável. Cada lista é um desfecho distinto, nunca um agregado."""

    linked: list[str] = field(default_factory=list)
    already_linked: list[str] = field(default_factory=list)
    conflict: list[dict] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)
    orphan_in_attio: list[str] = field(default_factory=list)
    dry_run: bool = True

    @property
    def wrote_anything(self) -> bool:
        return bool(self.linked) and not self.dry_run

    def as_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "linked": sorted(self.linked),
            "already_linked": sorted(self.already_linked),
            "conflict": self.conflict,
            "ambiguous": sorted(self.ambiguous),
            "orphan_in_attio": sorted(self.orphan_in_attio),
        }


def _index_by_external_id(entries: Iterable[AttioEntry]) -> tuple[dict[str, AttioEntry], list[str]]:
    """Indexa por ``external_lead_id``. Id repetido ⇒ ambíguo, e sai do índice.

    Duas entradas do Attio para o mesmo lead externo não têm resposta única.
    Escolher a primeira seria heurística — o par vira relatório.
    """
    index: dict[str, AttioEntry] = {}
    ambiguous: set[str] = set()
    for e in entries:
        key = (e.external_lead_id or "").strip()
        if not key:
            continue
        if key in index and index[key].person_id != e.person_id:
            ambiguous.add(key)
        index[key] = e
    for key in ambiguous:
        index.pop(key, None)
    return index, sorted(ambiguous)


def reconcile_attio_links(
    session: Session,
    tenant_id: uuid.UUID,
    entries: Iterable[AttioEntry],
    source_system: str = "rumy",
    dry_run: bool = True,
) -> ReconciliationReport:
    """Preenche ``attio_person_id`` (e company, quando inequívoco) nos links.

    Nunca cria link: se o ``external_lead_id`` do Attio não existe no domínio,
    ele é reportado como órfão. Criar a partir do espelho inverteria a
    autoridade — o banco é a fonte, o Attio é o espelho.
    """
    index, ambiguous = _index_by_external_id(entries)
    report = ReconciliationReport(dry_run=dry_run, ambiguous=ambiguous)

    links = (
        session.query(CrmLeadLink)
        .filter(
            CrmLeadLink.tenant_id == tenant_id,
            CrmLeadLink.source_system == source_system,
            CrmLeadLink.external_lead_id.in_(list(index.keys()) or [""]),
        )
        .all()
    )
    by_external = {str(link.external_lead_id): link for link in links}

    for external_id, entry in index.items():
        link = by_external.get(external_id)
        if link is None:
            report.orphan_in_attio.append(external_id)
            continue

        # str() explícito: o atributo é Column no plano de tipos do SQLAlchemy e
        # comparar Column em contexto booleano é erro de tipo, não de runtime.
        current = str(link.attio_person_id) if link.attio_person_id is not None else None
        if current and current != entry.person_id:
            # Duas verdades sobre a mesma pessoa. Sobrescrever destruiria a
            # anterior sem ninguém saber qual estava certa.
            report.conflict.append(
                {
                    "external_lead_id": external_id,
                    "no_dominio": current,
                    "no_attio": entry.person_id,
                }
            )
            continue
        if current == entry.person_id:
            report.already_linked.append(external_id)
            continue

        if not dry_run:
            link.attio_person_id = entry.person_id  # type: ignore[assignment]
            # Company só quando inequívoca: vem preenchida e o domínio está vazio.
            if entry.company_id and link.attio_company_id is None:
                link.attio_company_id = entry.company_id  # type: ignore[assignment]
        report.linked.append(external_id)

    if not dry_run and report.linked:
        session.flush()

    logger.info("attio_reconciliation %s", report.as_dict())
    return report
