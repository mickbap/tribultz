"""add_early_adopter_cockpit — Cockpit Operacional do Programa Early Adopters (RFC-0024)

Estende a fundação do RFC-0017/ADR-0008 (``early_adopters``/``early_grants``, já em
produção) com o que o cockpit precisa:

- ``early_adopters``: cadastrais expandidos (cargo, cidade, uf, erp, qtd_cnpjs,
  volume_nfe_mensal_aprox), ``proxima_acao``, ``owner_email`` (dono interno da
  conta), ``recognition`` (early_adopter → founding_partner, RFC-0024) e os campos
  de Conversão (Tela 02) — todos nullable/com default seguro, aditivos.
- Reconcilia o enum ``origem`` para o conjunto da RFC-0024 (LinkedIn, Instagram,
  Indicação, Cliente 6tech, Google, Site, Evento, Outro), migrando os valores
  legados do RFC-0017 (microsoft_forms, contato_direto) para os mais próximos.
- ``early_adopter_journey_events``: apenas eventos de jornada lançados manualmente
  pelo Owner — os automáticos (1º login, XML recebido) são derivados ao vivo do
  próprio sistema no endpoint de detalhe (RFC-0024, princípio "observar, não
  replicar"), nunca duplicados aqui.
- ``customer_evidence``: captura de Discovery (RFC-0019/ADR-0005) por
  participante — nunca altera o Brain automaticamente.
- ``early_adopter_tera``: registro manual do TERA (upload/link de PDF) — a
  geração automática depende do RFC-0018, ainda não construído.
- ``users.first_login_at``/``users.last_login_at``: necessários para popular
  "Primeiro/Último login" da jornada sem tabela adicional (não existia nenhum
  rastro de login persistido).

Revision ID: 2026_07_19_0028
Revises: 2026_07_16_0027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "2026_07_19_0028"
down_revision = "2026_07_16_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users.first_login_at / last_login_at ───────────────────────────────
    op.add_column("users", sa.Column("first_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))

    # ── early_adopters: cadastrais expandidos + próxima ação + owner + reconhecimento ──
    op.add_column("early_adopters", sa.Column("cargo", sa.String(length=100), nullable=True))
    op.add_column("early_adopters", sa.Column("cidade", sa.String(length=100), nullable=True))
    op.add_column("early_adopters", sa.Column("uf", sa.String(length=2), nullable=True))
    op.add_column("early_adopters", sa.Column("erp", sa.String(length=100), nullable=True))
    op.add_column("early_adopters", sa.Column("qtd_cnpjs", sa.Integer(), nullable=True))
    op.add_column("early_adopters", sa.Column("volume_nfe_mensal_aprox", sa.Integer(), nullable=True))
    op.add_column("early_adopters", sa.Column("proxima_acao", sa.Text(), nullable=True))
    op.add_column("early_adopters", sa.Column("owner_email", sa.String(length=255), nullable=True))
    op.add_column(
        "early_adopters",
        sa.Column("recognition", sa.String(length=20), nullable=False, server_default="early_adopter"),
    )

    # ── Conversão (Tela 02) ──────────────────────────────────────────────────
    op.add_column("early_adopters", sa.Column("conversion_interesse", sa.String(length=20), nullable=True))
    op.add_column("early_adopters", sa.Column("conversion_motivo", sa.Text(), nullable=True))
    op.add_column("early_adopters", sa.Column("conversion_plano_slug", sa.String(length=50), nullable=True))
    op.add_column("early_adopters", sa.Column("conversion_data", sa.DateTime(timezone=True), nullable=True))
    op.add_column("early_adopters", sa.Column("conversion_valor_cents", sa.Integer(), nullable=True))
    op.add_column("early_adopters", sa.Column("conversion_origem", sa.String(length=100), nullable=True))

    # ── Reconciliação do enum origem (RFC-0017 → RFC-0024) ──────────────────
    # Valores legados sem correspondência direta migram para "outro" — não há
    # perda de sinal crítico (a empresa continua identificável pelos demais
    # campos); poucas linhas existem em produção (feature em operação há <2 semanas).
    op.execute("UPDATE early_adopters SET origem = 'outro' WHERE origem IN ('microsoft_forms', 'contato_direto')")

    # ── early_adopter_journey_events (só eventos manuais) ───────────────────
    op.create_table(
        "early_adopter_journey_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("early_adopter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["early_adopter_id"], ["early_adopters.id"], ondelete="CASCADE", name="fk_ea_journey_adopter_id"),
    )
    op.create_index("ix_ea_journey_adopter_id", "early_adopter_journey_events", ["early_adopter_id"])

    # ── customer_evidence (Discovery — RFC-0019/ADR-0005) ───────────────────
    op.create_table(
        "customer_evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("early_adopter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column("autor", sa.String(length=200), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["early_adopter_id"], ["early_adopters.id"], ondelete="CASCADE", name="fk_customer_evidence_adopter_id"),
    )
    op.create_index("ix_customer_evidence_adopter_id", "customer_evidence", ["early_adopter_id"])

    # ── early_adopter_tera (registro manual — RFC-0018 fica para a geração) ──
    op.create_table(
        "early_adopter_tera",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("early_adopter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("versao", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="rascunho"),
        sa.Column("responsavel", sa.String(length=200), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("pdf_link", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["early_adopter_id"], ["early_adopters.id"], ondelete="CASCADE", name="fk_ea_tera_adopter_id"),
    )
    op.create_index("ix_ea_tera_adopter_id", "early_adopter_tera", ["early_adopter_id"])


def downgrade() -> None:
    op.drop_index("ix_ea_tera_adopter_id", table_name="early_adopter_tera")
    op.drop_table("early_adopter_tera")
    op.drop_index("ix_customer_evidence_adopter_id", table_name="customer_evidence")
    op.drop_table("customer_evidence")
    op.drop_index("ix_ea_journey_adopter_id", table_name="early_adopter_journey_events")
    op.drop_table("early_adopter_journey_events")

    for col in (
        "conversion_origem", "conversion_valor_cents", "conversion_data",
        "conversion_plano_slug", "conversion_motivo", "conversion_interesse",
        "recognition", "owner_email", "proxima_acao", "volume_nfe_mensal_aprox",
        "qtd_cnpjs", "erp", "uf", "cidade", "cargo",
    ):
        op.drop_column("early_adopters", col)

    op.drop_column("users", "last_login_at")
    op.drop_column("users", "first_login_at")
