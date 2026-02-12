"""Task C – What-if simulation: evaluate tax impact under alternate rate scenarios."""

import json
import logging
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.celery_app import celery
from app.tools.postgres_tool import get_tax_rules, insert_audit_log

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")


# ── Simulation table bootstrap ───────────────────────────────
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


def _ensure_table():
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
) -> dict:
    """
    Run multiple what-if scenarios against a base amount.

    Each scenario: {
        "name": "CBS + 2pp",
        "cbs_rate_override": "0.1125",   # optional – if omitted uses DB rate
        "ibs_rate_override": "0.1200",   # optional
    }

    1. Fetch current CBS/IBS rates from Postgres
    2. For each scenario, apply override rates and calculate
    3. Persist the simulation result in a `simulations` table
    4. Audit-log the run
    """
    _ensure_table()

    ref = date.fromisoformat(ref_date) if ref_date else date.today()
    base = Decimal(base_amount)

    # Current rates
    rules = get_tax_rules(tenant_id, ["STD_CBS", "STD_IBS"], ref)
    current_rates = {r["tax_type"]: Decimal(str(r["rate"])) for r in rules}
    current_cbs = current_rates.get("CBS", Decimal("0"))
    current_ibs = current_rates.get("IBS", Decimal("0"))

    # Base scenario (current rules)
    base_cbs_amt = (base * current_cbs).quantize(TWO_PLACES, ROUND_HALF_UP)
    base_ibs_amt = (base * current_ibs).quantize(TWO_PLACES, ROUND_HALF_UP)
    base_total_tax = base_cbs_amt + base_ibs_amt

    base_scenario = {
        "name": "Cenário Atual",
        "cbs_rate": str(current_cbs),
        "ibs_rate": str(current_ibs),
        "cbs_amount": str(base_cbs_amt),
        "ibs_amount": str(base_ibs_amt),
        "total_tax": str(base_total_tax),
        "effective_rate": str((base_total_tax / base * 100).quantize(TWO_PLACES)) + "%",
    }

    # What-if scenarios
    scenario_results: list[dict] = []
    for sc in scenarios:
        cbs_override = sc.get("cbs_rate_override")
        ibs_override = sc.get("ibs_rate_override")
        sc_cbs = Decimal(str(cbs_override)) if cbs_override is not None else current_cbs
        sc_ibs = Decimal(str(ibs_override)) if ibs_override is not None else current_ibs

        sc_cbs_amt = (base * sc_cbs).quantize(TWO_PLACES, ROUND_HALF_UP)
        sc_ibs_amt = (base * sc_ibs).quantize(TWO_PLACES, ROUND_HALF_UP)
        sc_total = sc_cbs_amt + sc_ibs_amt
        delta = sc_total - base_total_tax

        scenario_results.append({
            "name": sc.get("name", "unnamed"),
            "cbs_rate": str(sc_cbs),
            "ibs_rate": str(sc_ibs),
            "cbs_amount": str(sc_cbs_amt),
            "ibs_amount": str(sc_ibs_amt),
            "total_tax": str(sc_total),
            "effective_rate": str((sc_total / base * 100).quantize(TWO_PLACES)) + "%",
            "delta_vs_current": str(delta),
            "delta_pct": str(((delta / base_total_tax) * 100).quantize(TWO_PLACES)) + "%" if base_total_tax else "N/A",
        })

    # Persist to simulations table
    from sqlalchemy import text as sa_text
    from app.database import SessionLocal
    import uuid

    sim_id = str(uuid.uuid4())
    full_result = {
        "base_amount": base_amount,
        "reference_date": ref.isoformat(),
        "base_scenario": base_scenario,
        "scenarios": scenario_results,
    }

    db = SessionLocal()
    try:
        db.execute(
            sa_text("""
                INSERT INTO simulations (id, tenant_id, name, base_scenario, scenarios, result)
                VALUES (CAST(:id AS uuid), CAST(:tid AS uuid), :name,
                        CAST(:base AS jsonb), CAST(:scenarios AS jsonb), CAST(:result AS jsonb))
            """),
            {
                "id": sim_id,
                "tid": tenant_id,
                "name": simulation_name,
                "base": json.dumps(base_scenario, default=str),
                "scenarios": json.dumps(scenario_results, default=str),
                "result": json.dumps(full_result, default=str),
            },
        )
        db.commit()
    finally:
        db.close()

    # Audit
    audit = insert_audit_log(
        tenant_id=tenant_id,
        action="whatif_simulation",
        entity_type="simulation",
        entity_id=sim_id,
        payload={"name": simulation_name, "scenarios_count": len(scenarios)},
    )

    full_result["simulation_id"] = sim_id
    full_result["audit_id"] = audit["id"]

    logger.info("Task C [%s] simulation=%s scenarios=%d", tenant_slug, sim_id, len(scenarios))
    return full_result
