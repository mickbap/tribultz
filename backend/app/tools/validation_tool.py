"""ValidationTool – payload validation, tolerances, and rule consistency."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from app.tools.postgres_tool import get_tax_rules

TWO_PLACES = Decimal("0.01")
DEFAULT_TOLERANCE = Decimal("0.01")   # R$ 0.01 rounding tolerance


# ── 1. Validate Payload ──────────────────────────────────────
def validate_payload(payload: dict, required_fields: list[str]) -> dict:
    """
    Check that a payload dict contains all required fields
    and none of them are empty / None.
    Returns {valid: bool, missing: [...], empty: [...]}.
    """
    missing = [f for f in required_fields if f not in payload]
    empty = [
        f for f in required_fields
        if f in payload and (payload[f] is None or str(payload[f]).strip() == "")
    ]
    return {
        "valid": len(missing) == 0 and len(empty) == 0,
        "missing": missing,
        "empty": empty,
    }


# ── 2. Validate with Tolerance ───────────────────────────────
def validate_with_tolerance(
    declared: Decimal | float | str,
    calculated: Decimal | float | str,
    tolerance: Decimal | float | str = DEFAULT_TOLERANCE,
) -> dict:
    """
    Check if |declared - calculated| <= tolerance.
    Returns {match: bool, declared, calculated, diff, tolerance}.
    """
    d = Decimal(str(declared)).quantize(TWO_PLACES, ROUND_HALF_UP)
    c = Decimal(str(calculated)).quantize(TWO_PLACES, ROUND_HALF_UP)
    t = Decimal(str(tolerance)).quantize(TWO_PLACES, ROUND_HALF_UP)
    diff = abs(d - c)
    return {
        "match": diff <= t,
        "declared": str(d),
        "calculated": str(c),
        "diff": str(diff),
        "tolerance": str(t),
    }


# ── 3. Validate Rule Consistency ─────────────────────────────
def validate_rule_consistency(
    tenant_id: str,
    rule_codes: list[str],
    ref_date: Optional[date] = None,
) -> dict:
    """
    Check that all rule_codes exist and are active for the given date.
    Returns {consistent: bool, found: [...], missing: [...], rules: [...]}.
    """
    ref = ref_date or date.today()
    rules = get_tax_rules(tenant_id, rule_codes, ref)

    found_codes = {r["rule_code"] for r in rules}
    missing = [c for c in rule_codes if c not in found_codes]

    return {
        "consistent": len(missing) == 0,
        "reference_date": ref.isoformat(),
        "found": sorted(found_codes),
        "missing": missing,
        "rules": rules,
    }


# ── 4. Validate Invoice Items ────────────────────────────────
def validate_invoice_items(
    tenant_id: str,
    items: list[dict],
    ref_date: Optional[date] = None,
    tolerance: Decimal | float | str = DEFAULT_TOLERANCE,
) -> dict:
    """
    Full validation of a list of invoice items against stored tax rules.
    Each item must have: base_amount, cbs_rule_code, ibs_rule_code,
    declared_cbs, declared_ibs.

    Returns per-item pass/fail plus a summary.
    """
    ref = ref_date or date.today()
    tol = Decimal(str(tolerance))

    # Collect all unique rule codes
    all_codes = set()
    for it in items:
        all_codes.add(it.get("cbs_rule_code", "STD_CBS"))
        all_codes.add(it.get("ibs_rule_code", "STD_IBS"))

    rules = get_tax_rules(tenant_id, list(all_codes), ref)
    rate_map: dict[str, Decimal] = {
        (r["rule_code"], r["tax_type"]): Decimal(str(r["rate"]))
        for r in rules
    }

    results = []
    all_pass = True

    for idx, it in enumerate(items):
        base = Decimal(str(it.get("base_amount", "0")))
        cbs_code = it.get("cbs_rule_code", "STD_CBS")
        ibs_code = it.get("ibs_rule_code", "STD_IBS")

        cbs_rate = rate_map.get((cbs_code, "CBS"))
        ibs_rate = rate_map.get((ibs_code, "IBS"))

        item_result: dict[str, Any] = {"index": idx, "sku": it.get("sku", "")}

        if cbs_rate is None:
            item_result["cbs_error"] = f"Rule '{cbs_code}' (CBS) not found"
            item_result["cbs_pass"] = False
            all_pass = False
        else:
            calc_cbs = (base * cbs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
            decl_cbs = Decimal(str(it.get("declared_cbs", "0"))).quantize(TWO_PLACES, ROUND_HALF_UP)
            cbs_diff = abs(calc_cbs - decl_cbs)
            item_result["cbs_rate"] = str(cbs_rate)
            item_result["cbs_calculated"] = str(calc_cbs)
            item_result["cbs_declared"] = str(decl_cbs)
            item_result["cbs_diff"] = str(cbs_diff)
            item_result["cbs_pass"] = cbs_diff <= tol
            if not item_result["cbs_pass"]:
                all_pass = False

        if ibs_rate is None:
            item_result["ibs_error"] = f"Rule '{ibs_code}' (IBS) not found"
            item_result["ibs_pass"] = False
            all_pass = False
        else:
            calc_ibs = (base * ibs_rate).quantize(TWO_PLACES, ROUND_HALF_UP)
            decl_ibs = Decimal(str(it.get("declared_ibs", "0"))).quantize(TWO_PLACES, ROUND_HALF_UP)
            ibs_diff = abs(calc_ibs - decl_ibs)
            item_result["ibs_rate"] = str(ibs_rate)
            item_result["ibs_calculated"] = str(calc_ibs)
            item_result["ibs_declared"] = str(decl_ibs)
            item_result["ibs_diff"] = str(ibs_diff)
            item_result["ibs_pass"] = ibs_diff <= tol
            if not item_result["ibs_pass"]:
                all_pass = False

        results.append(item_result)

    return {
        "status": "PASS" if all_pass else "FAIL",
        "total_items": len(items),
        "passed": sum(1 for r in results if r.get("cbs_pass", False) and r.get("ibs_pass", False)),
        "failed": sum(1 for r in results if not (r.get("cbs_pass", False) and r.get("ibs_pass", False))),
        "tolerance": str(tol),
        "reference_date": ref.isoformat(),
        "items": results,
    }
