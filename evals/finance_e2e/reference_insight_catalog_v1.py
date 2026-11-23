#!/usr/bin/env python3
"""Source-derived comparison IDs for reference-only financial candidates.

Call the SEC source-row preflight before building a catalog. This module only
computes differences between the selected displayed rows; it does not certify
filing completeness, causal interpretation, or insight quality.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import build_postcorrection_v4_event_preflight as source_batch


def _number(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("selected source value is not decimal") from exc
    if not result.is_finite():
        raise ValueError("selected source value is not finite")
    return result


def _text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def build_catalog(symbol: str, packet: dict) -> dict:
    """Include every selected metric with a type-compatible quarter pair."""
    normalized = source_batch._normalize(symbol, packet)
    before = normalized["facts"]["baseline"]
    after = normalized["facts"]["event"]
    rows = {}
    for metric in sorted(before.keys() & after.keys()):
        baseline, event = before[metric], after[metric]
        if (baseline["unit"], baseline["basis"]) != (event["unit"], event["basis"]):
            raise ValueError(f"quarterly unit/basis mismatch: {metric}")
        old, new = _number(baseline["value"]), _number(event["value"])
        delta = new - old
        identifier = f"SEQ:{metric}"
        rows[identifier] = {
            "metric": metric,
            "baseline_value": _text(old),
            "event_value": _text(new),
            "delta_value": _text(delta),
            "direction": "increase" if delta > 0 else "decrease" if delta < 0 else "flat",
            "unit": baseline["unit"],
            "basis": baseline["basis"],
            "precision": "difference_of_selected_displayed_values",
        }
    if not rows:
        raise ValueError("selected packet has no comparable source rows")
    source_index = source_batch._source_index()
    baseline_ref, baseline_filed = source_batch._source_ref(
        packet["baseline"], source_index)
    event_ref, event_filed = source_batch._source_ref(
        packet["event"], source_index)
    return {
        "case_id": packet["case_id"],
        "symbol": symbol,
        "scope": "selected_source_rows_not_full_filing",
        "comparison": "sequential_event_minus_baseline_not_year_over_year",
        "baseline": {"period": packet["baseline"]["period"],
                     "source_id": baseline_ref["id"],
                     "source_url": baseline_ref["url"],
                     "source_sha256": baseline_ref["sha256"],
                     "filing_date": baseline_filed},
        "event": {"period": packet["event"]["period"],
                  "source_id": event_ref["id"],
                  "source_url": event_ref["url"],
                  "source_sha256": event_ref["sha256"],
                  "filing_date": event_filed},
        "rows": rows,
    }


def render_catalog(catalog: dict) -> str:
    """Render the entire trusted table, so agent selection cannot hide rows."""
    lines = [
        f"{catalog['symbol']} selected SEC comparisons: "
        f"{catalog['baseline']['period']} -> {catalog['event']['period']}",
        f"Baseline source: {catalog['baseline']['source_id']} "
        f"SHA-256 {catalog['baseline']['source_sha256']} "
        f"{catalog['baseline']['source_url']}",
        f"Event source: {catalog['event']['source_id']} "
        f"SHA-256 {catalog['event']['source_sha256']} "
        f"{catalog['event']['source_url']}",
        "Comparison ID | metric | baseline | event | signed change | direction | basis",
    ]
    for identifier, row in catalog["rows"].items():
        lines.append(
            f"{identifier} | {row['metric']} | {row['baseline_value']} {row['unit']} | "
            f"{row['event_value']} {row['unit']} | {row['delta_value']} {row['unit']} | "
            f"{row['direction']} | {row['basis']}"
        )
    lines.append("Numbers are selected displayed-row arithmetic, not causal explanations.")
    return "\n".join(lines)
