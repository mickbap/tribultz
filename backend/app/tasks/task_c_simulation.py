"""Task C - What-if simulation: evaluate tax impact under alternate rate scenarios."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.celery_app import celery
from app.services.simples_ibs_cbs_comparison import (
    CenarioComparativo,
    CustoFinanceiroHipotetico,
    PremissaCreditoProprio,
    PremissasCreditoB2B,
    PremissasModalidade,
    comparar_simples_ibs_cbs,
    parametros_simples_informados,
)
from app.tools.postgres_tool import get_tax_rules, insert_audit_log, job_status_update

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")

_SIMULATIONS_DDL = """
CREATE TABLE IF NOT EXISTS simulations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name          VARCHAR(200)  NOT NULL,
    base_scenario JSONB         NOT NULL DEFAULT '{}',
    scenarios     JSONB         NOT NULL DEFAULT '[]',
    result        JSONB,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_simulations_tenant ON simulations(tenant_id);
"""


def _optional_decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


def _credito_proprio_from_payload(payload: dict) -> PremissaCreditoProprio:
    return PremissaCreditoProprio(
        informacao_minima_suficiente=bool(payload.get("informacao_minima_suficiente", False)),
        aquisicoes_potencialmente_creditaveis=_optional_decimal(
            payload.get("aquisicoes_potencialmente_creditaveis")
        ),
        coeficiente_credito_potencial_estimado=_optional_decimal(
            payload.get("coeficiente_credito_potencial_estimado")
        ),
    )


def _custo_financeiro_from_payload(
    payload: dict | None,
) -> CustoFinanceiroHipotetico | None:
    if payload is None:
        return None
    return CustoFinanceiroHipotetico(
        montante=Decimal(str(payload["montante"])),
        periodo_dias=int(payload["periodo_dias"]),
        taxa_custo_capital_anual=Decimal(str(payload["taxa_custo_capital_anual"])),
    )


def _premissas_modalidade_from_payload(payload: dict) -> PremissasModalidade:
    return PremissasModalidade(
        credito_proprio=_credito_proprio_from_payload(payload.get("credito_proprio") or {}),
        custo_incremental_conformidade=_optional_decimal(
            payload.get("custo_incremental_conformidade")
        ),
        custo_financeiro=_custo_financeiro_from_payload(payload.get("custo_financeiro_hipotetico")),
    )


def _cenario_simples_from_payload(payload: dict) -> CenarioComparativo:
    credito_b2b = payload.get("credito_b2b") or {}
    return CenarioComparativo(
        nome=str(payload["nome"]),
        receita_base=_optional_decimal(payload.get("receita_base")),
        aliquota_cbs_regime_regular_cenario=_optional_decimal(
            payload.get("aliquota_cbs_regime_regular_cenario")
        ),
        aliquota_ibs_regime_regular_cenario=_optional_decimal(
            payload.get("aliquota_ibs_regime_regular_cenario")
        ),
        regime_unico=_premissas_modalidade_from_payload(payload.get("regime_unico") or {}),
        regime_regular=_premissas_modalidade_from_payload(payload.get("regime_regular") or {}),
        credito_b2b=PremissasCreditoB2B(
            informacao_minima_suficiente=bool(
                credito_b2b.get("informacao_minima_suficiente", False)
            ),
            credito_potencial_estimado=_optional_decimal(
                credito_b2b.get("credito_potencial_estimado")
            ),
        ),
    )


def _ensure_table() -> None:
    from sqlalchemy import text

    from app.database import SessionLocal

    db = SessionLocal()
    try:
        db.execute(text(_SIMULATIONS_DDL))
        db.commit()
    finally:
        db.close()


@celery.task(name="task_c_whatif_simulation", bind=True, max_retries=3)
def task_c_whatif_simulation(
    self,
    tenant_id: str,
    tenant_slug: str,
    simulation_name: str,
    base_amount: str,
    scenarios: list[dict],
    ref_date: str | None = None,
    transaction_id: str | None = None,
) -> dict:
    """
    Run multiple what-if scenarios against a base amount.
    """
    task_id = str(self.request.id) if self.request and self.request.id else ""
    if task_id:
        job_status_update(job_id=task_id, status="RUNNING", transaction_id=transaction_id)

    try:
        _ensure_table()

        ref = date.fromisoformat(ref_date) if ref_date else date.today()
        base = Decimal(base_amount)

        rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
        current_rates = {rule["tax_type"]: Decimal(str(rule["rate"])) for rule in rules}
        current_cbs = current_rates.get("CBS", Decimal("0"))
        current_ibs = current_rates.get("IBS", Decimal("0"))

        base_cbs_amount = (base * current_cbs).quantize(TWO_PLACES, ROUND_HALF_UP)
        base_ibs_amount = (base * current_ibs).quantize(TWO_PLACES, ROUND_HALF_UP)
        base_total_tax = base_cbs_amount + base_ibs_amount

        base_scenario = {
            "name": "Cenario Atual",
            "cbs_rate": str(current_cbs),
            "ibs_rate": str(current_ibs),
            "cbs_amount": str(base_cbs_amount),
            "ibs_amount": str(base_ibs_amount),
            "total_tax": str(base_total_tax),
            "effective_rate": str((base_total_tax / base * 100).quantize(TWO_PLACES)) + "%",
        }

        scenario_results: list[dict[str, str]] = []
        for scenario in scenarios:
            cbs_override = scenario.get("cbs_rate_override")
            ibs_override = scenario.get("ibs_rate_override")
            scenario_cbs = Decimal(str(cbs_override)) if cbs_override is not None else current_cbs
            scenario_ibs = Decimal(str(ibs_override)) if ibs_override is not None else current_ibs

            scenario_cbs_amount = (base * scenario_cbs).quantize(TWO_PLACES, ROUND_HALF_UP)
            scenario_ibs_amount = (base * scenario_ibs).quantize(TWO_PLACES, ROUND_HALF_UP)
            scenario_total = scenario_cbs_amount + scenario_ibs_amount
            delta = scenario_total - base_total_tax

            scenario_results.append(
                {
                    "name": str(scenario.get("name", "unnamed")),
                    "cbs_rate": str(scenario_cbs),
                    "ibs_rate": str(scenario_ibs),
                    "cbs_amount": str(scenario_cbs_amount),
                    "ibs_amount": str(scenario_ibs_amount),
                    "total_tax": str(scenario_total),
                    "effective_rate": str((scenario_total / base * 100).quantize(TWO_PLACES)) + "%",
                    "delta_vs_current": str(delta),
                    "delta_pct": (
                        str(((delta / base_total_tax) * 100).quantize(TWO_PLACES)) + "%"
                        if base_total_tax
                        else "N/A"
                    ),
                }
            )

        from sqlalchemy import text as sa_text
        from app.database import SessionLocal
        import uuid

        simulation_id = str(uuid.uuid4())
        full_result = {
            "base_amount": base_amount,
            "reference_date": ref.isoformat(),
            "base_scenario": base_scenario,
            "scenarios": scenario_results,
        }

        db = SessionLocal()
        try:
            db.execute(
                sa_text(
                    """
                    INSERT INTO simulations (id, tenant_id, name, base_scenario, scenarios, result)
                    VALUES (
                        CAST(:id AS uuid),
                        CAST(:tenant_id AS uuid),
                        :name,
                        CAST(:base_scenario AS jsonb),
                        CAST(:scenarios AS jsonb),
                        CAST(:result AS jsonb)
                    )
                    """
                ),
                {
                    "id": simulation_id,
                    "tenant_id": tenant_id,
                    "name": simulation_name,
                    "base_scenario": json.dumps(base_scenario, default=str),
                    "scenarios": json.dumps(scenario_results, default=str),
                    "result": json.dumps(full_result, default=str),
                },
            )
            db.commit()
        finally:
            db.close()

        audit = insert_audit_log(
            tenant_id=tenant_id,
            action="whatif_simulation",
            entity_type="simulation",
            entity_id=simulation_id,
            payload={"name": simulation_name, "scenarios_count": len(scenarios)},
        )

        full_result["simulation_id"] = simulation_id
        full_result["audit_id"] = audit["id"]

        if task_id:
            job_status_update(
                job_id=task_id,
                status="SUCCESS",
                result=full_result,
                transaction_id=transaction_id,
            )

        logger.info("Task C [%s] simulation=%s scenarios=%d", tenant_slug, simulation_id, len(scenarios))
        return full_result
    except Exception as exc:
        if task_id:
            job_status_update(
                job_id=task_id,
                status="FAILED",
                error_message=str(exc),
                transaction_id=transaction_id,
            )
        raise


@celery.task(name="task_c_simples_ibs_cbs_comparison_v1", bind=True, max_retries=3)
def task_c_simples_ibs_cbs_comparison_v1(
    self,
    tenant_id: str,
    tenant_slug: str,
    simulation_name: str,
    aliquota_efetiva_cbs_simples: str | None,
    aliquota_efetiva_ibs_simples: str | None,
    scenarios: list[dict],
    transaction_id: str | None = None,
) -> dict:
    """Executa o comparativo v1 sem validar dados informados pelo cliente."""
    task_id = str(self.request.id) if self.request and self.request.id else ""
    if task_id:
        job_status_update(job_id=task_id, status="RUNNING", transaction_id=transaction_id)

    try:
        parametros = parametros_simples_informados(
            cbs=_optional_decimal(aliquota_efetiva_cbs_simples),
            ibs=_optional_decimal(aliquota_efetiva_ibs_simples),
        )
        result = comparar_simples_ibs_cbs(
            parametros=parametros,
            cenarios=[_cenario_simples_from_payload(item) for item in scenarios],
        )
        audit = insert_audit_log(
            tenant_id=tenant_id,
            action="simples_ibs_cbs_comparison_v1",
            entity_type="job",
            entity_id=task_id or None,
            payload={
                "simulation_name": simulation_name,
                "scenario_count": len(scenarios),
                "parametros_simples": result["PARAMETROS_SIMPLES"],
                "modelo": result["versao_modelo"],
            },
            transaction_id=transaction_id,
        )
        result["simulation_name"] = simulation_name
        result["audit_id"] = audit["id"]

        if task_id:
            job_status_update(
                job_id=task_id,
                status="SUCCESS",
                result=result,
                transaction_id=transaction_id,
            )
        logger.info(
            "Task C Simples v1 [%s] cenarios=%d audit=%s",
            tenant_slug,
            len(scenarios),
            audit["id"],
        )
        return result
    except Exception as exc:
        if task_id:
            job_status_update(
                job_id=task_id,
                status="FAILED",
                error_message=str(exc),
                transaction_id=transaction_id,
            )
        raise
