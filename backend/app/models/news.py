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
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
