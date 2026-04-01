"""Document model — tenant-scoped file management with S3 presigned upload flow."""

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import text

from app.database import Base


class Document(Base):
    __tablename__ = "documents"

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
    # Document classification
    doc_type = Column(String(50), nullable=False)  # "nfe", "nfse", "cte", "other"
    original_filename = Column(String(512), nullable=True)

    # S3 storage
    storage_key = Column(String(512), nullable=False, unique=True)

    # File metadata
    file_size = Column(Integer, nullable=True)  # bytes, filled on confirm
    content_type = Column(String(100), nullable=True)

    # Upload lifecycle
    # pending_upload → uploaded (PUT done, not yet confirmed) → confirmed / error
    status = Column(String(30), nullable=False, default="pending_upload")

    # Timestamps
    uploaded_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # presigned URL expiry
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Flexible fiscal metadata extracted from XML
    # Keys: chave_acesso, cnpj_emitente, cnpj_destinatario, valor_total, ncm, etc.
    fiscal_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
