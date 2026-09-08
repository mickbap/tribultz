"""Persistência de job/auditoria do comparativo Simples IBS/CBS v1."""

from __future__ import annotations

from unittest.mock import patch

from app.tasks.task_c_simulation import task_c_simples_ibs_cbs_comparison_v1


def test_task_preserva_tenant_trilha_e_estado_nao_validado() -> None:
    scenario = {
        "nome": "auditável",
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
        "credito_b2b": {
            "informacao_minima_suficiente": False,
            "credito_potencial_estimado": None,
        },
    }

    task_c_simples_ibs_cbs_comparison_v1.push_request(id="job-simples-v1")
    try:
        with (
            patch(
                "app.tasks.task_c_simulation.insert_audit_log",
                return_value={"id": "audit-simples-v1"},
            ) as audit,
            patch("app.tasks.task_c_simulation.job_status_update") as status,
        ):
            result = task_c_simples_ibs_cbs_comparison_v1.run(
                tenant_id="tenant-alpha",
                tenant_slug="alpha",
                simulation_name="Comparativo auditável",
                aliquota_efetiva_cbs_simples="0.01",
                aliquota_efetiva_ibs_simples="0.02",
                scenarios=[scenario],
            )
    finally:
        task_c_simples_ibs_cbs_comparison_v1.pop_request()

    assert result["audit_id"] == "audit-simples-v1"
    assert result["PARAMETROS_SIMPLES"]["ALIQUOTA_EFETIVA_CBS_SIMPLES"]["estado"] == (
        "NAO_VALIDADO"
    )
    assert audit.call_args.kwargs["tenant_id"] == "tenant-alpha"
    assert audit.call_args.kwargs["entity_id"] == "job-simples-v1"
    assert audit.call_args.kwargs["payload"]["parametros_simples"] == result[
        "PARAMETROS_SIMPLES"
    ]
    assert [call.kwargs["status"] for call in status.call_args_list] == ["RUNNING", "SUCCESS"]
    assert status.call_args_list[-1].kwargs["job_id"] == "job-simples-v1"
