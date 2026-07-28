"""ProspectIngestionRun — auditoria de cada execução de ingest_cnpj_dump.py
(Ordem Complementar à PO-2026-07-SALES-001, salvaguardas operacionais).

Cada execução real (sucesso, falha ou abortada por guarda de sanidade/layout)
grava uma linha aqui, append-only. É a base para: guarda de sanidade (compara
contra a última execução bem-sucedida com o mesmo target_cnaes), validação de
layout (hash + assinatura dos arquivos usados) e trava de sequenciamento
(score_and_select.py verifica se existe dedup posterior à ingestão mais recente).
"""

from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from app.database import Base

# running: em andamento; completed: sucesso; failed: erro inesperado;
# aborted_sanity_check: guarda de volume/variação disparou; aborted_layout_mismatch:
# layout dos arquivos não bate com o esperado.
INGESTION_RUN_STATUSES: tuple[str, ...] = (
    "running",
    "completed",
    "failed",
    "aborted_sanity_check",
    "aborted_layout_mismatch",
)


class ProspectIngestionRun(Base):
    __tablename__ = "prospect_ingestion_runs"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    dump_reference = Column(String(32), nullable=False)
    target_cnaes = Column(JSONB, nullable=False)  # lista ordenada, usada para comparar execuções compatíveis
    download_date = Column(Date, nullable=False)  # informado pelo operador — não é inferível de forma confiável

    # Métricas de volume (guarda de sanidade)
    total_estabelecimentos_scanned = Column(Integer, nullable=True)
    total_target_cnae_found = Column(Integer, nullable=True)
    total_ativas = Column(Integer, nullable=True)
    total_consolidated = Column(Integer, nullable=True)
    tolerance_params = Column(JSONB, nullable=False, server_default="{}")  # snapshot dos limites usados

    # Proveniência/layout
    file_count = Column(Integer, nullable=True)
    files_sha256 = Column(JSONB, nullable=True)  # {nome_do_arquivo: sha256}
    layout_signature = Column(Text, nullable=True)  # ex.: "empresas:7campos;estabelecimentos:30campos;..."

    status = Column(String(24), nullable=False, server_default="running")
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
