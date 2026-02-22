from __future__ import annotations

import json
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal, Optional, cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crews.executor import TribultzChatOpsExecutor
from app.models.chat import Conversation, Message
from app.schemas.chat import ChatResult, JobEvidence
from app.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

Intent = Literal["validate", "unknown"]

_TEMPLATE_CANDIDATES = [
    Path(__file__).resolve().parents[1] / "templates" / "ptbr_tax_response_template.md",
    Path(__file__).resolve().parents[2] / "crews" / "tribultz_chatops" / "templates" / "ptbr_tax_response_template.md",
    Path(__file__).resolve().parents[3] / "crews" / "tribultz_chatops" / "templates" / "ptbr_tax_response_template.md",
]

_TEMPLATE_FALLBACK = """# Resultado (Tribultz - Padrao Fiscal BR)

## Resultado
- **Status:** {STATUS}
- **Resumo executivo:** {RESUMO_EXECUTIVO}

## Evidencias
> Cada evidencia deve ser tipada e rastreavel (Job/Audit).
- **Job:** [{JOB_LABEL}]({JOB_HREF}) - `job_id={JOB_ID}`
- **Audit (se aplicavel):** {AUDIT_REF}

## Observacoes / Premissas
- **Premissas consideradas:** {PREMISSAS}
- **Limites / Incertezas:** {LIMITES}
- **Recomendacao pratica:** {RECOMENDACAO}

## Detalhamento tecnico (opcional)
- **Regras avaliadas (CBS/IBS):** {REGRAS}
- **Itens com divergencia:** {DIVERGENCIAS}

## Valores (se houver)
- **Valores em BRL:** {VALORES_BRL}
"""


def classify_intent(message: str) -> Intent:
    """MVP classifier (keyword based)."""
    m = message.lower()
    if "validate" in m or "validar" in m or "validacao" in m:
        return "validate"
    return "unknown"


def format_brl(value: Any) -> str:
    """Format numeric values as BRL (R$ 1.234,56)."""
    if value is None or value == "":
        return "—"
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    us = f"{amount:,.2f}"
    br = us.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {br}"


def render_br_tax_response(
    *,
    status_text: str,
    resumo_executivo: str,
    job_label: str,
    job_href: str,
    job_id: str,
    audit_ref: str = "—",
    premissas: str = "—",
    limites: str = "—",
    recomendacao: str = "—",
    regras: str = "—",
    divergencias: str = "—",
    valores_brl: Any = None,
) -> str:
    template = _TEMPLATE_FALLBACK
    for path in _TEMPLATE_CANDIDATES:
        if path.exists():
            template = path.read_text(encoding="utf-8")
            break
    return template.format(
        STATUS=status_text,
        RESUMO_EXECUTIVO=resumo_executivo,
        JOB_LABEL=job_label,
        JOB_HREF=job_href,
        JOB_ID=job_id,
        AUDIT_REF=audit_ref,
        PREMISSAS=premissas,
        LIMITES=limites,
        RECOMENDACAO=recomendacao,
        REGRAS=regras,
        DIVERGENCIAS=divergencias,
        VALORES_BRL=format_brl(valores_brl),
    )


class ChatService:
    """
    Orchestrates chat interactions:
      1. Rate Limiting
      2. Conversation persistence/ownership
      3. Intent classification
      4. Task trigger
    """

    def __init__(self, db: Session):
        self.db = db
        self.executor = TribultzChatOpsExecutor()
        self.rate_limiter = RateLimiter()

    async def handle_message(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        message: str,
        conversation_id: Optional[UUID],
    ) -> ChatResult:
        self.rate_limiter.check_or_raise(str(user_id))

        if conversation_id:
            conv = self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == tenant_id,
                )
            ).scalar_one_or_none()
            if not conv:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found",
                )
        else:
            conv = Conversation(tenant_id=tenant_id, user_id=user_id, title=message[:50])
            self.db.add(conv)
            self.db.flush()
            conversation_id = cast(UUID, conv.id)

        self.db.add(
            Message(
                conversation_id=conversation_id,
                role="user",
                content=message,
            )
        )

        intent = classify_intent(message)
        response_markdown = ""
        evidence_list: list[JobEvidence] = []

        if intent == "validate":
            try:
                job_id = await self.executor.trigger_task_a(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    message=message,
                )
                job_href = f"/jobs/{job_id}"
                job_label = "Validation Job"
                response_markdown = render_br_tax_response(
                    status_text="OK",
                    resumo_executivo=(
                        "Iniciei a validacao fiscal e gerei um Job rastreavel. "
                        "Acompanhe o processamento no link abaixo."
                    ),
                    job_label=job_label,
                    job_href=job_href,
                    job_id=str(job_id),
                    audit_ref="—",
                    premissas="Informacoes fornecidas na mensagem e regras do tenant.",
                    limites="Resultado sujeito a premissas e legislacao vigente.",
                    recomendacao="Abra o Job para evidencias tipadas e trilha de auditoria.",
                    regras="CBS/IBS (Task A).",
                    divergencias="—",
                    valores_brl=None,
                )

                evidence_list.append(
                    JobEvidence(
                        type="job",
                        job_id=job_id,
                        href=job_href,
                        label=job_label,
                    )
                )
            except Exception as exc:
                logger.error("Chat execution error: %s", exc)
                response_markdown = "I encountered an error trying to start validation. Please try again."
        else:
            response_markdown = (
                "I'm not sure how to help with that. Currently I can assist with "
                "**validating invoices** (CBS/IBS)."
            )

        evidence_dicts = [e.model_dump() for e in evidence_list]

        def uuid_serializer(obj: Any) -> Any:
            if isinstance(obj, UUID):
                return str(obj)
            return obj

        self.db.add(
            Message(
                conversation_id=conversation_id,
                role="assistant",
                content=response_markdown,
                metadata_=json.loads(json.dumps({"evidence": evidence_dicts}, default=uuid_serializer)),
            )
        )
        self.db.commit()

        return ChatResult(
            conversation_id=conversation_id,
            response_markdown=response_markdown,
            evidence=evidence_list,
        )
