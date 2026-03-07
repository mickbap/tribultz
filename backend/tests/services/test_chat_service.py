from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

from app.crews.executor import TribultzChatOpsExecutor
from app.services.chat_service import ChatService, render_br_tax_response


def test_render_br_tax_response_has_required_sections() -> None:
    job_id = str(uuid4())
    markdown = render_br_tax_response(
        status_text="OK",
        resumo_executivo="Resumo de teste",
        job_label="Validation Job",
        job_href=f"/jobs/{job_id}",
        job_id=job_id,
        premissas="Premissa",
        limites="Limite",
        recomendacao="Recomendacao",
        regras="Regra",
        divergencias="Nenhuma",
        valores_brl=1234.56,
    )

    assert "Padrão Fiscal BR" in markdown
    assert "## Resultado" in markdown
    assert "## Evidências" in markdown
    assert "## Observações" in markdown
    assert f"/jobs/{job_id}" in markdown
    assert f"job_id={job_id}" in markdown
    assert "R$ 1.234,56" in markdown


def test_handle_message_passes_crew_output_through() -> None:
    tenant_id = uuid4()
    user_id = uuid4()
    conversation_id = uuid4()
    job_id = uuid4()

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = SimpleNamespace(
        id=conversation_id,
        tenant_id=tenant_id,
    )

    service = ChatService(db=db)
    service.rate_limiter = Mock()
    service.rate_limiter.check_or_raise = Mock()

    job_href = f"/jobs/{job_id}"
    mock_markdown = f"Validation started.\n\nJob: `{job_id}`"
    mock_evidence = [
        {"type": "job", "job_id": str(job_id), "href": job_href, "label": "Validation job"}
    ]

    executor = Mock(spec=TribultzChatOpsExecutor)
    executor.handle_message = AsyncMock(return_value=(mock_markdown, mock_evidence))
    service.executor = cast(TribultzChatOpsExecutor, executor)

    result = asyncio.run(
        service.handle_message(
            tenant_id=tenant_id,
            user_id=user_id,
            message="Validate invoice INV-999",
            conversation_id=conversation_id,
        )
    )

    assert result.response_markdown == mock_markdown
    assert len(result.evidence) == 1
    assert result.evidence[0].type == "job"
    assert result.evidence[0].href == job_href
    assert str(result.evidence[0].job_id) == str(job_id)

    executor.handle_message.assert_called_once()
    call_kwargs = executor.handle_message.call_args.kwargs
    assert call_kwargs["tenant_id"] == tenant_id
    assert call_kwargs["user_id"] == user_id
    assert call_kwargs["message"] == "Validate invoice INV-999"

    db.commit.assert_called_once()
