"""add_news_seed_key — idempotência do seed do changelog sob concorrência (#638)

O seed do changelog roda no `lifespan` do FastAPI e era idempotente por
SELECT-depois-INSERT, sem constraint. Os processos que sobem juntos no deploy
liam "não existe" ao mesmo tempo e inseriam todos — o feed público chegou a
servir cada entrada em duplicata, com `created_at` separados por microssegundos.

Mecanismo: coluna `seed_key` com índice único. O Postgres trata NULLs como
distintos entre si, então:

  - linhas do catálogo de seed carregam a chave → não podem duplicar;
  - linhas publicadas pelo endpoint ficam com NULL → podem repetir título
    legitimamente (ex.: advisory mensal de re-sync da tabela cClassTrib).

Índice único global em (title, category) resolveria a primeira metade e
violaria a segunda — por isso não foi usado.

A deduplicação é ESCOPADA ao catálogo de seed de propósito: varrer a tabela
inteira por (title, category) poderia apagar conteúdo editorial legitimamente
repetido, que é justamente a propriedade que este trabalho precisa preservar.

Revision ID: 2026_08_16_0038
Revises: 2026_08_12_0037
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "2026_08_16_0038"
down_revision = "2026_08_12_0037"
branch_labels = None
depends_on = None

# Mapa congelado no tempo (título, categoria) → chave estável. Espelha o
# catálogo de `app/services/news_seed.py` NESTA data; migrations não seguem a
# evolução do código, e não devem.
SEED_CATALOG: list[tuple[str, str, str]] = [
    (
        "Lançamento da Memória Fiscal Multi-tenant",
        "Feature",
        "feature-memoria-fiscal-multitenant",
    ),
    (
        "03/08/2026: SEFAZ passa a rejeitar NF-e sem IBS/CBS no Regime Normal (CRT 3)",
        "Advisory",
        "advisory-2026-08-03-crt3-rejeicao-1115",
    ),
    (
        "NT 2025.002 v1.50: novo grupo para o regime monofásico de combustíveis (CBS/IBS)",
        "Advisory",
        "advisory-nt-2025-002-v150-monofasico",
    ),
    (
        "Novos leiautes: NT 2026.002 (presencial/não presencial) e NT 2026.003 (DANFE Simplificado T2)",
        "Advisory",
        "advisory-nt-2026-002-003-leiautes",
    ),
    (
        "Split Payment: Receita Federal e CGIBS publicam Manual de Integração e Swagger da Plataforma Pública",
        "Advisory",
        "advisory-split-payment-manual-swagger",
    ),
]


def upgrade() -> None:
    op.add_column("news", sa.Column("seed_key", sa.String(length=80), nullable=True))

    conn = op.get_bind()

    # 1) Deduplicação defensiva, antes de qualquer constraint. Mantém a cópia
    #    mais antiga; `(created_at, id)` dá ordem total, então nunca sobram duas
    #    linhas empatadas no timestamp.
    conn.execute(
        sa.text(
            """
            DELETE FROM news a
            USING news b
            WHERE a.title = b.title
              AND a.category = b.category
              AND (a.created_at, a.id) > (b.created_at, b.id)
              AND (a.title, a.category) IN (
                  SELECT * FROM unnest(
                      CAST(:titles AS text[]),
                      CAST(:categories AS text[])
                  )
              )
            """
        ),
        {
            "titles": [t for t, _, _ in SEED_CATALOG],
            "categories": [c for _, c, _ in SEED_CATALOG],
        },
    )

    # 2) Backfill: as linhas sobreviventes do catálogo passam a carregar a chave,
    #    preservando `created_at` (a ordem do feed público não muda).
    for title, category, key in SEED_CATALOG:
        conn.execute(
            sa.text(
                "UPDATE news SET seed_key = :key WHERE title = :title AND category = :category"
            ),
            {"key": key, "title": title, "category": category},
        )

    # 3) Só agora o índice único — com os duplicados já removidos, não falha.
    op.create_index("ix_news_seed_key", "news", ["seed_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_news_seed_key", table_name="news")
    op.drop_column("news", "seed_key")
