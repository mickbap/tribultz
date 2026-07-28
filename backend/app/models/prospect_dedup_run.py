"""ProspectDedupRun — auditoria de cada execução de dedup_prospects.py
(Ordem Complementar à PO-2026-07-SALES-001, salvaguardas operacionais).

Existe para a trava de sequenciamento: score_and_select.py só roda se o
ProspectDedupRun concluído mais recente for posterior ao ProspectIngestionRun
concluído mais recente — nunca pontua dados parcialmente processados.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class ProspectDedupRun(Base):
    __tablename__ = "prospect_dedup_runs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    groups_merged = Column(Integer, nullable=True)
    orgs_merged = Column(Integer, nullable=True)
    domains_skipped_too_large = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, server_default="completed")  # running|completed|failed

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
