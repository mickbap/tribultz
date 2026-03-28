from __future__ import annotations

import logging

from sqlalchemy import inspect, select

from app.database import SessionLocal, engine
from app.models.news import News

logger = logging.getLogger(__name__)

DEFAULT_NEWS_TITLE = "Lançamento da Memória Fiscal Multi-tenant"
DEFAULT_NEWS_DESCRIPTION = (
    "Ativamos a memória fiscal persistente com isolamento por tenant, "
    "armazenamento em Redis e recuperação de precedentes após reinício da API."
)
DEFAULT_NEWS_CATEGORY = "Feature"


def ensure_default_news_entry() -> None:
    if not inspect(engine).has_table("news"):
        return

    with SessionLocal() as db:
        existing = db.scalar(
            select(News.id).where(
                News.title == DEFAULT_NEWS_TITLE,
                News.category == DEFAULT_NEWS_CATEGORY,
            )
        )
        if existing is not None:
            return

        db.add(
            News(
                title=DEFAULT_NEWS_TITLE,
                description=DEFAULT_NEWS_DESCRIPTION,
                category=DEFAULT_NEWS_CATEGORY,
            )
        )
        db.commit()
        logger.info("default_news_seeded title=%s", DEFAULT_NEWS_TITLE)
