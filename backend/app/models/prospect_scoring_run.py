"""ProspectScoringRun — histórico append-only de execuções do pipeline de prospecção
comercial direta (PO-2026-07-SALES-001, Fase 1).

Cada execução real de score_and_select.py insere uma linha aqui (nunca sobrescreve) —
é o que permite, em fase futura, reprocessar uma lista antiga com outra versão de
rubrica e comparar estatisticamente os resultados sem qualquer migration nova.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from app.database import Base


class ProspectScoringRun(Base):
    __tablename__ = "prospect_scoring_runs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    rubric_version = Column(String(32), nullable=False)
    rubric_checksum = Column(String(64), nullable=False)  # sha256 do YAML, detecta edição
    rubric_snapshot = Column(JSONB, nullable=False, server_default="{}")  # pesos completos usados — reprodutibilidade total mesmo se o YAML mudar/sumir
    source_dump_reference = Column(String(32), nullable=False)
    params = Column(JSONB, nullable=False, server_default="{}")  # snapshot dos args da CLI
    candidate_count = Column(Integer, nullable=False)  # pós consolidação+dedup+supressão
    selected_count = Column(Integer, nullable=False)  # tamanho do Top-N realmente escrito
    output_uri = Column(String(500), nullable=False)
    output_checksum = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, server_default="completed")  # running|completed|failed
    error_message = Column(Text, nullable=True)
    run_started_at = Column(DateTime(timezone=True), nullable=False)
    run_finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
