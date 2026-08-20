"""Idempotência do seed do changelog sob concorrência (#638, L1.8 / decisão D2).

Duas propriedades, ambas exigidas — a segunda é o que descarta um índice único
global em (title, category):

  1. N processos subindo juntos e M reinícios produzem exatamente o mesmo
     conjunto de entradas, sem cópias.
  2. Títulos legitimamente repetíveis continuam publicáveis pelo endpoint.

O defeito original: `ensure_*` lia com SELECT e inseria depois. Os processos que
sobem juntos no deploy (api/worker/beat, cada um executando o lifespan) liam
"não existe" ao mesmo tempo e inseriam todos. Em produção o feed serviu 10
linhas onde deveria haver 5, com `created_at` separados por microssegundos.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.models.news import News
from app.services.news_seed import (
    DEFAULT_NEWS_SEED_KEY,
    REGULATORY_ADVISORIES,
    ensure_default_news_entry,
    ensure_regulatory_advisories,
)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
VerifySession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

SEED_KEYS = {DEFAULT_NEWS_SEED_KEY, *(e["key"] for e in REGULATORY_ADVISORIES)}


def _limpar_seed() -> None:
    with VerifySession() as db:
        db.query(News).filter(News.seed_key.in_(SEED_KEYS)).delete(synchronize_session=False)
        db.commit()


def _contagem_por_chave() -> dict[str, int]:
    with VerifySession() as db:
        linhas = db.execute(
            select(News.seed_key, func.count())
            .where(News.seed_key.in_(SEED_KEYS))
            .group_by(News.seed_key)
        ).all()
    return {k: n for k, n in linhas}


def _semear_tudo() -> None:
    ensure_default_news_entry()
    ensure_regulatory_advisories()


def test_seed_cria_o_catalogo_completo():
    _limpar_seed()
    try:
        _semear_tudo()
        assert _contagem_por_chave() == {k: 1 for k in SEED_KEYS}
    finally:
        _limpar_seed()


def test_reinicios_sucessivos_nao_duplicam():
    """M reinícios em série — o caso que acontece a cada deploy."""
    _limpar_seed()
    try:
        for _ in range(4):
            _semear_tudo()
        assert _contagem_por_chave() == {k: 1 for k in SEED_KEYS}
    finally:
        _limpar_seed()


def test_processos_concorrentes_nao_duplicam():
    """N processos subindo juntos — o caso que produziu as cópias em produção.

    É este teste que falha sob o SELECT-depois-INSERT antigo: as threads leem
    "não existe" na mesma janela e todas inserem.
    """
    _limpar_seed()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: _semear_tudo(), range(8)))

        contagem = _contagem_por_chave()
        assert contagem == {k: 1 for k in SEED_KEYS}, (
            f"seed duplicou sob concorrência: {contagem}"
        )
    finally:
        _limpar_seed()


def test_endpoint_pode_repetir_titulo_legitimamente():
    """Segunda metade da propriedade — a que um índice único global quebraria.

    Um changelog fiscal repete títulos de propósito (ex.: advisory mensal de
    re-sync da tabela cClassTrib). Linhas publicadas fora do catálogo ficam com
    `seed_key` NULL, e o Postgres trata NULLs como distintos entre si.
    """
    titulo = f"Re-sync da tabela cClassTrib — teste {uuid.uuid4().hex[:8]}"
    with VerifySession() as db:
        try:
            for _ in range(3):
                db.add(News(title=titulo, description="Mesma manchete, outro mês.", category="Advisory"))
                db.commit()

            total = db.scalar(select(func.count()).select_from(News).where(News.title == titulo))
            assert total == 3, "publicação editorial não pode ser bloqueada por título repetido"
        finally:
            db.query(News).filter(News.title == titulo).delete(synchronize_session=False)
            db.commit()


def test_linhas_do_catalogo_carregam_seed_key():
    """A chave é o que separa catálogo de conteúdo editorial."""
    _limpar_seed()
    try:
        _semear_tudo()
        with VerifySession() as db:
            sem_chave = db.scalar(
                select(func.count())
                .select_from(News)
                .where(News.title == REGULATORY_ADVISORIES[0]["title"], News.seed_key.is_(None))
            )
        assert sem_chave == 0
    finally:
        _limpar_seed()
