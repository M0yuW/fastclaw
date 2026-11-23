#!/usr/bin/env python3
"""Conservative, post-hoc red-flag screen for reference-only insights.

This is a development diagnostic, not a financial-quality judge. Its alerts
require claim-level review; absence of alerts is not a quality pass. It never
changes or re-scores the sealed v1 observations.
"""

from __future__ import annotations

import re


PROFIT_METRICS = frozenset({
    "gaap_operating_income", "gaap_pretax_income", "gaap_income_before_taxes",
    "gaap_net_income", "gaap_net_income_common",
})
UNSUPPORTED_BENCHMARK = re.compile(
    r"\b(?:quality of the beat|beat expectations|beat consensus|"
    r"missed expectations|missed consensus|earnings beat|earnings miss)\b",
    re.IGNORECASE,
)
LOWER_TAX_DRAG = re.compile(
    r"\b(?:smaller|lower|reduced|less)\s+(?:effective\s+)?tax\s+"
    r"(?:drag|burden|expense)\b|\btax\s+expense\s+(?:fell|declined|decreased)\b",
    re.IGNORECASE,
)
HIGHER_TAX_DRAG = re.compile(
    r"\b(?:larger|higher|increased|greater)\s+(?:effective\s+)?tax\s+"
    r"(?:drag|burden|expense)\b|\btax\s+expense\s+(?:rose|increased)\b",
    re.IGNORECASE,
)


def screen(catalog: dict, candidate: dict, state: dict) -> dict:
    """Return reproducible alerts; do not certify non-alerted prose."""
    if not isinstance(candidate, dict):
        return {"alerts": ["candidate_not_object"], "quality_pass": None}
    interpretation = candidate.get("interpretation") or {}
    if not isinstance(interpretation, dict):
        interpretation = {}
    argument = " ".join(str(interpretation.get(key) or "")
                        for key in ("implication", "counterevidence"))
    theses = state.get("theses") or [] if isinstance(state, dict) else []
    reviews = theses[0].get("reviews") or [] if len(theses) == 1 else []
    saved_rationale = reviews[0].get("rationale") or "" if len(reviews) == 1 else ""
    claims = argument + " " + saved_rationale
    alerts = []

    # A sequential filing pair contains no consensus or guidance-versus-actual
    # benchmark. Only affirmative benchmark language is screened; disclaimer
    # paragraphs are intentionally excluded to avoid negation false positives.
    if UNSUPPORTED_BENCHMARK.search(argument):
        alerts.append("unsupported_benchmark_language")

    rows = catalog.get("rows") or {}
    tax_directions = {row.get("direction") for row in rows.values()
                      if row.get("metric") in {
                          "gaap_income_tax_expense", "gaap_tax_expense_magnitude"}}
    if tax_directions == {"increase"} and LOWER_TAX_DRAG.search(claims):
        alerts.append("tax_direction_contradiction")
    elif tax_directions == {"decrease"} and HIGHER_TAX_DRAG.search(claims):
        alerts.append("tax_direction_contradiction")

    selection = candidate.get("selected_comparisons") or {}
    if isinstance(selection, dict):
        support = selection.get("support") or []
        counter = selection.get("counterevidence") or []
        if isinstance(support, list) and isinstance(counter, list):
            support_directions = [rows[ref]["direction"] for ref in support
                                  if ref in rows
                                  and rows[ref].get("metric") in PROFIT_METRICS
                                  and rows[ref].get("direction") != "flat"]
            if len(support_directions) >= 2 and len(set(support_directions)) == 1:
                direction = support_directions[0]
                if any(ref in rows
                       and rows[ref].get("metric") in PROFIT_METRICS
                       and rows[ref].get("direction") == direction
                       for ref in counter):
                    alerts.append("profit_reference_role_conflict")

    return {"alerts": alerts, "quality_pass": None}
