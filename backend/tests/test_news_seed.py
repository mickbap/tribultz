"""Tests for the regulatory advisories seed (#407 — campanha 03/08)."""

import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models.news import News
from app.services.news_seed import REGULATORY_ADVISORIES, ensure_regulatory_advisories

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tribultz:tribultz@localhost:5432/tribultz")
engine = create_engine(DATABASE_URL)
VerifySession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _cleanup(titles: set[str]) -> None:
    with VerifySession() as db:
        db.query(News).filter(News.title.in_(titles)).delete(synchronize_session=False)
        db.commit()


def test_ensure_regulatory_advisories_seeds_all_four():
    titles = {entry["title"] for entry in REGULATORY_ADVISORIES}
    _cleanup(titles)  # garante estado limpo mesmo se um run anterior falhou no meio
    try:
        ensure_regulatory_advisories()

        with VerifySession() as db:
            rows = db.scalars(select(News).where(News.category == "Advisory")).all()
            assert {row.title for row in rows} == titles
    finally:
        _cleanup(titles)


def test_ensure_regulatory_advisories_is_idempotent():
    titles = {entry["title"] for entry in REGULATORY_ADVISORIES}
    _cleanup(titles)
    try:
        ensure_regulatory_advisories()
        ensure_regulatory_advisories()

        with VerifySession() as db:
            rows = db.scalars(select(News).where(News.category == "Advisory")).all()
            assert len(rows) == len(REGULATORY_ADVISORIES)
    finally:
        _cleanup(titles)
