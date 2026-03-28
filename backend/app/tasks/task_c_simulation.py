"""Task C - What-if simulation: evaluate tax impact under alternate rate scenarios."""

from __future__ import annotations

import json
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.celery_app import celery
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
