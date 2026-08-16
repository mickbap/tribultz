from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class News(Base):
    __tablename__ = "news"
    __table_args__ = (
        CheckConstraint(
            "category IN ('Feature', 'Fix', 'Security', 'Advisory')",
            name="news_category_check",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    # Chave estável da entrada no catálogo de seed (#638). NULL para tudo que é
    # publicado pelo endpoint. O índice único sobre esta coluna é o que impede o
    # seed de duplicar sob concorrência — e, como o Postgres trata NULLs como
    # distintos entre si, não restringe em nada a publicação editorial, que pode
    # repetir título legitimamente (ex.: advisory mensal de re-sync do cClassTrib).
    seed_key = Column(String(80), nullable=True, unique=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
