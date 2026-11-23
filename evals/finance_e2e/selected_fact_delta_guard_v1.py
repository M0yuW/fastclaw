#!/usr/bin/env python3
"""Deterministic, source-packet-level deltas and explicit mix residuals.

Call a source auditor before this module. It checks arithmetic on the frozen
selected facts, not whether those facts were transcribed correctly from SEC.
It never treats an accounting contribution as a causal business explanation.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


DELTA_UNITS = {
    "USD_million_rounded": "USD_million",
    "USD_thousand_reported": "USD_thousand",
    "USD_billion_reported": "USD_billion",
    "USD_per_share_reported": "USD_per_share",
    "million_shares_reported": "million_shares",
    "million_accounts_reported": "million_accounts",
    "thousand_shares_reported": "thousand_shares",
    "percent": "percentage_points",
}
SUPPORTED_UNITS = set(DELTA_UNITS)


def _text(number: Decimal) -> str:
    return format(number.normalize(), "f")


def _facts(section: dict) -> dict:
    facts = section["facts"]
    if len({fact["id"] for fact in facts}) != len(facts):
        raise ValueError("duplicate fact ID")
    if len({fact["metric"] for fact in facts}) != len(facts):
        raise ValueError("duplicate metric name")
    return {fact["metric"]: fact for fact in facts}


def derive(packet: dict) -> dict:
    before, after = _facts(packet["baseline"]), _facts(packet["event"])
    if before.keys() != after.keys():
        raise ValueError("baseline and event metrics differ")
    rows = {}
    for metric in sorted(before):
        old, new = before[metric], after[metric]
        unit = old["unit"]
        if unit not in SUPPORTED_UNITS or new["unit"] != unit:
            raise ValueError(f"unsupported or mismatched unit: {metric}")
        left, right = Decimal(str(old["value"])), Decimal(str(new["value"]))
        if not left.is_finite() or not right.is_finite():
            raise ValueError(f"nonfinite selected fact: {metric}")
        delta = right - left
        relative = ((delta / left) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP) if left > 0 else None
        rows[metric] = {
            "baseline_fact_id": old["id"], "event_fact_id": new["id"],
            "baseline_value": _text(left), "event_value": _text(right),
            "unit": unit,
            "delta_value": _text(delta),
            "delta_unit": DELTA_UNITS[unit],
            "precision": "difference_of_displayed_values",
            "relative_percent_of_baseline": _text(relative) if relative is not None else None,
        }
    return {"case_id": packet["case_id"],
            "baseline_source_sha256": packet["baseline"]["source_sha256"],
            "event_source_sha256": packet["event"]["source_sha256"],
            "rows": rows}


def decompose_change(bundle: dict, total_metric: str, component_metrics: list[str]) -> dict:
    """Show the unlisted residual; no causal attribution is inferred."""
    rows = bundle["rows"]
    if not component_metrics or len(set(component_metrics)) != len(component_metrics):
        raise ValueError("components must be distinct and nonempty")
    if total_metric in component_metrics or total_metric not in rows:
        raise ValueError("invalid total metric")
    if any(metric not in rows for metric in component_metrics):
        raise ValueError("unknown component metric")
    if any(rows[metric]["delta_unit"] != "USD_million"
           for metric in [total_metric, *component_metrics]):
        raise ValueError("mix decomposition needs USD million levels")
    total = Decimal(rows[total_metric]["delta_value"])
    components = {metric: Decimal(rows[metric]["delta_value"])
                  for metric in component_metrics}
    residual = total - sum(components.values(), Decimal(0))
    return {"case_id": bundle["case_id"], "total_metric": total_metric,
            "total_delta_usd_million": _text(total),
            "components_delta_usd_million": {key: _text(value)
                                             for key, value in components.items()},
            "unlisted_residual_usd_million": _text(residual),
            "fully_accounted_by_listed_components": residual == 0,
            "meaning": "arithmetic mix only; not a causal explanation"}


def render_trusted_numeric_context(bundle: dict, decompositions=()) -> str:
    """Render host-computed facts for a later model-facing workflow.

    This deliberately omits packet interpretation checks, quality labels, and
    model conclusions. It is not a substitute for the source audit or the
    post-run claim-level quality judgment.
    """
    lines = [
        f"Case: {bundle['case_id']}",
        f"Baseline SEC SHA-256: {bundle['baseline_source_sha256']}",
        f"Event SEC SHA-256: {bundle['event_source_sha256']}",
        "Displayed-value comparisons (same metric and basis):",
        "metric | baseline fact/value | event fact/value | change | relative change",
    ]
    for metric, row in bundle["rows"].items():
        relative = (f"{row['relative_percent_of_baseline']}% of baseline"
                    if row["relative_percent_of_baseline"] is not None else "n/a")
        lines.append(
            f"{metric} | {row['baseline_fact_id']}={row['baseline_value']} "
            f"{row['unit']} | {row['event_fact_id']}={row['event_value']} "
            f"{row['unit']} | {row['delta_value']} {row['delta_unit']} | {relative}"
        )
    for item in decompositions:
        if item["case_id"] != bundle["case_id"]:
            raise ValueError("mix decomposition belongs to another case")
        parts = ", ".join(f"{key}={value} USD_million"
                          for key, value in item["components_delta_usd_million"].items())
        lines.append(
            f"Arithmetic mix for {item['total_metric']}: total "
            f"{item['total_delta_usd_million']} USD_million; listed components "
            f"{parts}; unlisted residual {item['unlisted_residual_usd_million']} "
            "USD_million. This is not a causal explanation."
        )
    lines.append(
        "Boundary: source-selected displayed values only; no causal driver, "
        "durability, valuation, or trading conclusion is established by this table."
    )
    return "\n".join(lines)
