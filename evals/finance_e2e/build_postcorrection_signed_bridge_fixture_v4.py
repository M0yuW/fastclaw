#!/usr/bin/env python3
"""Free development fixtures with source-defined signed accounting bridges.

This uses the already-seen v2 issuer frame to develop a correction, not an
untouched holdout or an authorization for model calls. V2/v3 inputs stay frozen.
"""

from __future__ import annotations

import json
from decimal import Decimal

import build_postcorrection_event_preflight_v2 as v2
from accounting_bridge_catalog_v4 import BRIDGES
from selected_fact_delta_guard_v1 import derive
from selected_fact_signed_bridge_v4 import signed_bridge


def _number(value: Decimal) -> str:
    return format(value.normalize(), "f")


def render_bridge(label: str, bundle: dict, total: str,
                  components: dict[str, int]) -> str:
    checked = signed_bridge(bundle, total, components)
    if not checked["fully_reconciles_both_periods"]:
        raise ValueError(f"source-defined bridge does not fully reconcile: {label}")
    parts = []
    contributions = []
    for metric, sign in components.items():
        parts.append(("+" if sign > 0 else "−") + metric)
        delta = Decimal(bundle["rows"][metric]["delta_value"]) * sign
        contributions.append(("+" if delta >= 0 else "−") + _number(abs(delta)))
    total_delta = bundle["rows"][total]["delta_value"]
    return (f"Source-defined accounting bridge for {label}: {total} = "
            + " ".join(parts) + ". "
            + f"Displayed-value change: {' '.join(contributions)} = {total_delta} "
            + f"{checked['unit']}; baseline, event, and change residuals are all 0. "
            + "This is an accounting identity, not an economic/causal driver.")


def prepare() -> dict:
    original = v2.preflight()  # Re-audits sources, packet locks, periods and values.
    fixtures = original["fixtures"]
    if {fixture["runtime_symbol"] for fixture in fixtures} != set(v2.READY):
        raise ValueError("v2 source frame changed")
    bridge_count = 0
    for fixture in fixtures:
        symbol = fixture["runtime_symbol"]
        if symbol not in BRIDGES:
            continue
        packet = json.loads(v2.READY[symbol][1].read_text())
        bundle = derive(packet)
        lines = []
        for label, total, components in BRIDGES[symbol]:
            lines.append(render_bridge(label, bundle, total, components))
            bridge_count += 1
        fixture["numeric_context"] += "\n" + "\n".join(lines)
    return {
        "status": "free_seen_case_bridge_development_not_holdout",
        "source_cases": len(fixtures),
        "bridge_cases": len(BRIDGES),
        "checked_bridges": bridge_count,
        "model_observations": 0,
        "fixtures": fixtures,
    }


if __name__ == "__main__":
    result = prepare()
    print(json.dumps({key: value for key, value in result.items()
                      if key != "fixtures"}, indent=2))
