#!/usr/bin/env python3
"""Derive auditable comparisons from source-locked fact records, without an LLM.

This deliberately computes only declared pairings and signed reconciliations.
It does not infer causal relationships, financial materiality or investment merit.
"""

from decimal import Decimal, ROUND_HALF_UP


UNIT_SCALE = {"USD_thousand": Decimal(1),
              "USD_million_rounded": Decimal(1000)}


def decimal_value(fact):
    value = fact.get("value")
    if isinstance(value, bool) or value is None:
        raise ValueError("fact value must be numeric")
    return Decimal(str(value))


def in_usd_thousand(fact):
    try:
        scale = UNIT_SCALE[fact["unit"]]
    except KeyError as exc:
        raise ValueError(f"unsupported comparison unit: {fact.get('unit')}") from exc
    return decimal_value(fact) * scale


def comparable_metric_name(metric):
    return metric.replace("_prior_year_same_quarter", "")


def compare(event_fact, baseline_fact, comparison_basis):
    """Compare a declared same-metric pair and retain precision limitations."""
    if comparable_metric_name(event_fact["metric"]) != comparable_metric_name(baseline_fact["metric"]):
        raise ValueError("comparison metrics differ")
    if event_fact["id"] == baseline_fact["id"]:
        raise ValueError("comparison needs distinct source facts")
    if comparison_basis not in {"sequential", "year_over_year"}:
        raise ValueError("comparison basis must be declared")
    event_value = in_usd_thousand(event_fact)
    baseline_value = in_usd_thousand(baseline_fact)
    delta = event_value - baseline_value
    rounded_input = any(fact["unit"] == "USD_million_rounded"
                        for fact in (event_fact, baseline_fact))
    if event_value < 0 and baseline_value < 0 and "loss" in event_fact["metric"]:
        direction = "loss_narrowed" if delta > 0 else ("loss_widened" if delta < 0 else "unchanged")
    elif delta > 0:
        direction = "increased"
    elif delta < 0:
        direction = "decreased"
    else:
        direction = "unchanged"
    # A percentage from two positive USD values has an unambiguous denominator;
    # do not print a misleading percentage for a signed loss or rounded input.
    percent = None
    if baseline_value > 0 and event_value >= 0 and not rounded_input:
        percent = ((delta / baseline_value) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {"event_fact_id": event_fact["id"],
            "baseline_fact_id": baseline_fact["id"],
            "metric": event_fact["metric"],
            "comparison_basis": comparison_basis,
            "event_usd_thousand": str(event_value),
            "baseline_usd_thousand": str(baseline_value),
            "delta_usd_thousand": str(delta),
            "direction": direction,
            "percent_change_of_baseline": str(percent) if percent is not None else None,
            "precision": "approximate_rounded_input" if rounded_input else "exact_from_selected_facts"}


def reconcile(base_fact, signed_adjustments, reported_fact):
    """Add the source's *signed* adjustments once, never subtract twice."""
    if not signed_adjustments:
        raise ValueError("reconciliation needs at least one adjustment")
    components = [base_fact, *signed_adjustments, reported_fact]
    if any(fact["unit"] != "USD_thousand" for fact in components):
        raise ValueError("reconciliation requires exact USD_thousand inputs")
    if len({fact["id"] for fact in components}) != len(components):
        raise ValueError("reconciliation fact IDs must be distinct")
    computed = decimal_value(base_fact) + sum(
        (decimal_value(fact) for fact in signed_adjustments), Decimal(0))
    reported = decimal_value(reported_fact)
    return {"base_fact_id": base_fact["id"],
            "signed_adjustment_fact_ids": [fact["id"] for fact in signed_adjustments],
            "reported_fact_id": reported_fact["id"],
            "computed_usd_thousand": str(computed),
            "reported_usd_thousand": str(reported),
            "residual_usd_thousand": str(computed - reported),
            "reconciled": computed == reported,
            "rule": "base_plus_source_signed_adjustments"}
