"""Partner — proveniência comercial (RFC-0025, Partner Attribution v1).

Um Partner responde, de forma permanente, "quem apresentou esta empresa à
Tribultz?". É **exclusivamente origem comercial** — nunca comissão, contrato ou
financeiro (guardrail RFC-0025). A origem vive em ``tenants.partner_id``.
"""

from __future__ import annotations

import re

from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import text

from app.database import Base

# Tipos de Partner (RFC-0025). Armazenados em minúsculo.
PARTNER_TYPES: tuple[str, ...] = (
    "lawyer",
    "accountant",
    "consultancy",
    "erp",
    "association",
    "influencer",
    "other",
)

PARTNER_STATUSES: tuple[str, ...] = ("active", "inactive")

# Partner Code: uppercase, sem acento/espaço, [A-Z0-9_-], 3–32 chars (RFC-0025).
_PARTNER_CODE_RE = re.compile(r"^[A-Z0-9_-]{3,32}$")


def normalize_partner_code(raw: str | None) -> str | None:
    """Normaliza um código para o formato canônico (uppercase, sem espaços).

    Retorna ``None`` quando o valor é vazio ou não bate com o formato — cabe ao
    chamador decidir o que fazer (na captura do /register, um código inválido
    apenas não vincula; no CRUD, é erro de validação).
    """
    if not raw:
        return None
    code = raw.strip().upper()
    if not _PARTNER_CODE_RE.match(code):
        return None
    return code


class Partner(Base):
    __tablename__ = "partners"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    type = Column(String(32), nullable=False, default="other")
    name = Column(String(200), nullable=False)
    company = Column(String(200), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    # Código único de indicação. Guardado sempre normalizado (uppercase).
    code = Column(String(32), nullable=False, unique=True)
    status = Column(String(16), nullable=False, server_default="active")
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
