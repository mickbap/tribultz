"""SQLAlchemy model for exception_requests table."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class ExceptionRequest(Base):
    __tablename__ = "exception_requests"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finding_id = Column(Text, nullable=False)
    rule_id = Column(Text, nullable=False)
    justification = Column(Text, nullable=False)
    status = Column(
        String(20),
        nullable=False,
        server_default="OPEN",
    )
    admin_name = Column(Text, nullable=False)
    admin_email = Column(Text, nullable=False)
    created_by = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_by = Column(Text, nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decision_comment = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('OPEN', 'APPROVED', 'REJECTED')",
            name="ck_exception_requests_status",
        ),
    )
