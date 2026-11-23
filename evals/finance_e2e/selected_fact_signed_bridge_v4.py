#!/usr/bin/env python3
"""Host-check a signed accounting identity on source-audited selected facts.

This does not infer a business cause. Call the issuer/source-row auditor first;
only use an identity whose signs and metric definitions the source establishes.
"""

from __future__ import annotations

from decimal import Decimal

from selected_fact_delta_guard_v1 import DELTA_UNITS


def signed_bridge(bundle: dict, total_metric: str,
                  signed_components: dict[str, int]) -> dict:
    rows = bundle["rows"]
    if (total_metric not in rows or not signed_components
            or total_metric in signed_components
            or any(metric not in rows or sign not in (-1, 1)
                   for metric, sign in signed_components.items())):
        raise ValueError("invalid signed accounting bridge")
    selected = [rows[metric] for metric in [total_metric, *signed_components]]
    unit = selected[0]["unit"]
    if (unit not in {"USD_million_rounded", "USD_thousand_reported",
                     "USD_billion_reported"}
            or any(row["unit"] != unit for row in selected)):
        raise ValueError("signed bridge requires matching currency levels")

    def residual(field: str) -> Decimal:
        return (Decimal(rows[total_metric][field])
                - sum((Decimal(rows[metric][field]) * sign
                       for metric, sign in signed_components.items()), Decimal(0)))

    baseline_residual = residual("baseline_value")
    event_residual = residual("event_value")
    delta_residual = residual("delta_value")
    if delta_residual != event_residual - baseline_residual:
        raise ValueError("inconsistent level and delta residuals")
    return {
        "case_id": bundle["case_id"],
        "total_metric": total_metric,
        "signed_components": signed_components,
        "unit": DELTA_UNITS[unit],
        "baseline_residual": str(baseline_residual),
        "event_residual": str(event_residual),
        "delta_residual": str(delta_residual),
        "fully_reconciles_both_periods": baseline_residual == event_residual == 0,
        "meaning": "source-defined accounting identity only; not a causal explanation",
    }
