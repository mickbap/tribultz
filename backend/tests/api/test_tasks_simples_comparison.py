"""Fronteira HTTP/tenant do comparativo Simples IBS/CBS v1."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.auth import User
from app.services.task_dispatcher import TaskEnqueueResponse


TENANT_ID = uuid4()
USER = User(
    id=uuid4(),
    email="simples-v1@example.invalid",
    tenant_id=TENANT_ID,
    full_name="Simples v1",
    is_active=True,
)


def _payload() -> dict:
    return {
        "simulation_name": "Comparativo controlado",
        "aliquota_efetiva_cbs_simples": "0.01",
        "aliquota_efetiva_ibs_simples": "0.02",
        "scenarios": [
            {
                "nome": "base",
                "receita_base": "1000",
                "aliquota_cbs_regime_regular_cenario": "0.03",
                "aliquota_ibs_regime_regular_cenario": "0.15",
                "regime_unico": {
                    "credito_proprio": {
                        "informacao_minima_suficiente": True,
                        "aquisicoes_potencialmente_creditaveis": "200",
                        "coeficiente_credito_potencial_estimado": "0.02",
                    },
                    "custo_incremental_conformidade": "10",
                },
                "regime_regular": {
                    "credito_proprio": {
                        "informacao_minima_suficiente": True,
                        "aquisicoes_potencialmente_creditaveis": "200",
                        "coeficiente_credito_potencial_estimado": "0.18",
                    },
                    "custo_incremental_conformidade": "30",
                },
            }
        ],
    }


@pytest.fixture()
def client() -> Iterator[TestClient]:
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_db] = lambda: object()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_dispatch_preserva_tenant_e_dados_informados_nao_recebem_estado_validado(
    client: TestClient,
) -> None:
    queued = TaskEnqueueResponse(task_id="job-v1", job_id="job-v1", status="QUEUED")
    with patch("app.routers.tasks.TaskDispatcher.dispatch", return_value=queued) as dispatch:
        response = client.post("/api/v1/tasks/simulate-simples-ibs-cbs", json=_payload())

    assert response.status_code == 202
    chamada = dispatch.call_args.kwargs
    assert chamada["tenant_id"] == str(TENANT_ID)
    assert chamada["definition"].job_type == "task_c_simples_ibs_cbs_comparison_v1"
    assert "estado" not in chamada["payload"]
    assert chamada["task_kwargs"]["aliquota_efetiva_cbs_simples"] == "0.01"


@pytest.mark.parametrize(
    "campo_proibido",
    [
        "cbs_regime_regular_como_proxy_do_simples",
        "media_historica_individual",
        "prazo_pagamento_fornecedor",
        "direito_a_credito_confirmado",
        "credito_apropriado",
    ],
)
def test_guardrails_rejeitam_inputs_proibidos(
    client: TestClient,
    campo_proibido: str,
) -> None:
    payload = _payload()
    payload["scenarios"][0][campo_proibido] = "1"

    response = client.post("/api/v1/tasks/simulate-simples-ibs-cbs", json=payload)

    assert response.status_code == 422


def test_cliente_nao_pode_autodeclarar_parametro_validado(client: TestClient) -> None:
    payload = _payload()
    payload["estado_parametro"] = "PARAMETRO_VALIDADO_TRIBULTZ"

    response = client.post("/api/v1/tasks/simulate-simples-ibs-cbs", json=payload)

    assert response.status_code == 422
