"""ProspectOrg — registro consolidado de escritório contábil para prospecção comercial
direta (PO-2026-07-SALES-001, Fase 1).

Um registro por CNPJ básico (matriz + filiais consolidadas). Origem: Dados Abertos do
CNPJ (Receita Federal). Não é tenant da Tribultz — é um alvo de prospecção, ainda sem
conta. Campos de endereço/contato/CNAE são carregados aqui mesmo sem uso pelo pré-score
da Fase 1, deliberadamente, para que a Fase 2 (agente de enriquecimento externo) não
precise de migration nova.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

from app.database import Base


class ProspectOrg(Base):
    __tablename__ = "prospect_orgs"
    __table_args__ = (
        CheckConstraint(
            "marketing_eligibility IN ('ELIGIBLE', 'INELIGIBLE')",
            name="ck_prospect_orgs_marketing_eligibility",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # ── Identidade / fatos da RF usados diretamente pelo pré-score ──
    cnpj_basico = Column(String(8), nullable=False, unique=True)
    porte = Column(String(2), nullable=False)
    # RF usa S/N/branco ("outros"); "branco" é colapsado em False — só o eixo
    # MEI/não-MEI importa para o pré-score da Fase 1 (ver scoring.py).
    opcao_mei = Column(Boolean, nullable=False, default=False)
    opcao_simples = Column(Boolean, nullable=False, default=False)
    capital_social = Column(Numeric(18, 2), nullable=False, default=0)
    situacao_cadastral = Column(String(2), nullable=False)
    data_inicio_atividade = Column(Date, nullable=True)
    qtd_socios = Column(Integer, nullable=False, default=0)
    qtd_estabelecimentos = Column(Integer, nullable=False, default=1)
    uf = Column(String(2), nullable=False)
    email = Column(String(255), nullable=True)
    email_domain = Column(String(255), nullable=True)
    email_domain_category = Column(String(20), nullable=True)  # ausente|gratuito|dominio_generico|dominio_nominal
    # Tipo do endereço (Ordem Complementar, item 6) — independente do domínio:
    # contato/comercial/financeiro/fiscal/suporte/nome_sobrenome/outro/ausente.
    # Peso baixo na rubrica (rubric_v2.yaml), só para desempate.
    email_type = Column(String(20), nullable=True)

    # ── Fatos da RF carregados só para não bloquear a Fase 2 (enriquecimento) ──
    cnpj_matriz = Column(String(14), nullable=False)
    razao_social = Column(String(200), nullable=False)
    nome_fantasia = Column(String(200), nullable=True)
    municipio_codigo = Column(String(7), nullable=True)
    municipio_nome = Column(String(120), nullable=True)
    logradouro = Column(String(200), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(200), nullable=True)
    bairro = Column(String(100), nullable=True)
    cep = Column(String(8), nullable=True)
    ddd_telefone1 = Column(String(4), nullable=True)
    telefone1 = Column(String(20), nullable=True)
    cnae_principal = Column(String(7), nullable=False)
    cnaes_secundarios = Column(JSONB, nullable=False, server_default="[]")
    data_situacao_cadastral = Column(Date, nullable=True)

    # ── Controle do pipeline ──
    dedup_status = Column(String(16), nullable=False, default="unique")  # unique|primary|merged
    merged_into_id = Column(
        UUID(as_uuid=True),
        ForeignKey("prospect_orgs.id", ondelete="SET NULL"),
        nullable=True,
    )
    pre_score = Column(Integer, nullable=True)
    pre_score_tier = Column(String(1), nullable=True)
    pre_score_rubric_version = Column(String(32), nullable=True)
    pre_scored_at = Column(DateTime(timezone=True), nullable=True)
    source_dump_reference = Column(String(32), nullable=False)  # ex.: "2026-07"

    # ── Proveniência e decisão de uso em marketing (Growth P0 / #733) ──
    # Não há motor jurídico aqui: a elegibilidade é uma decisão explícita,
    # registrada por processo humano/jurídico. O executor apenas aplica gates
    # fail-closed sobre a decisão e sua evidência mínima.
    marketing_origin = Column(String(120), nullable=True)
    marketing_collected_at = Column(Date, nullable=True)
    marketing_purpose = Column(String(160), nullable=True)
    marketing_legal_basis = Column(String(120), nullable=True)
    marketing_lia_evidence_ref = Column(String(500), nullable=True)
    marketing_eligibility = Column(
        String(16), nullable=False, default="INELIGIBLE", server_default="INELIGIBLE"
    )
    marketing_eligibility_reason = Column(String(240), nullable=True)
    marketing_eligibility_evaluated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
