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


def test_handle_message_validate_uses_br_template() -> None:
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

    executor = Mock(spec=TribultzChatOpsExecutor)
    executor.trigger_task_a = AsyncMock(return_value=job_id)
    service.executor = cast(TribultzChatOpsExecutor, executor)

    result = asyncio.run(
        service.handle_message(
            tenant_id=tenant_id,
            user_id=user_id,
            message="Validate invoice INV-999",
            conversation_id=conversation_id,
        )
    )

    assert "Padrão Fiscal BR" in result.response_markdown
    assert "## Resultado" in result.response_markdown
    assert "## Evidências" in result.response_markdown
    assert "## Observações" in result.response_markdown
    assert f"/jobs/{job_id}" in result.response_markdown
    assert str(job_id) in result.response_markdown

    assert len(result.evidence) == 1
    assert result.evidence[0].type == "job"
    assert result.evidence[0].href == f"/jobs/{job_id}"
    assert result.evidence[0].job_id == job_id
    db.commit.assert_called_once()
