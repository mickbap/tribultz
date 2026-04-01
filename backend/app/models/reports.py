"""Report model — tenant-scoped PDF report storage with S3 presigned download flow."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        UniqueConstraint("storage_key", name="uq_reports_storage_key"),
        CheckConstraint(
            "report_type IN ('validation', 'batch')",
            name="reports_report_type_check",
        ),
        CheckConstraint(
            "status IN ('generating', 'ready', 'error')",
            name="reports_status_check",
        ),
    )

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
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Job association (optional — may be null for ad-hoc reports)
    job_id = Column(String(36), nullable=True)

    # Report classification: "validation" | "batch"
    report_type = Column(String(30), nullable=False)

    # S3 storage
    storage_key = Column(String(512), nullable=False, unique=True)

    # File info
    file_size = Column(Integer, nullable=True)  # bytes

    # Deterministic SHA-256 of report input payload
    report_hash = Column(String(64), nullable=False)

    # Lifecycle: generating → ready | error
    status = Column(String(20), nullable=False, default="generating")

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
