#!/usr/bin/env python3
"""Developmental source-arithmetic red flags for a post-final candidate.

This is not a quality judge or a pre-commit ledger guard. It checks only
explicit statements whose truth can be resolved from comparable frozen rows.
Rules were designed after inspecting some v1 answers, so retrospective hits
are diagnostic rather than prospective guard-performance estimates.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from screen_reference_insight_semantics_v2 import screen as v2_screen


TAX_METRICS = (
    "gaap_income_tax_expense", "gaap_tax_expense", "gaap_tax_provision",
    "gaap_income_tax_provision", "income_tax_provision",
)
PRETAX_METRICS = (
    "gaap_pretax_income", "gaap_income_before_taxes",
    "gaap_income_before_income_taxes", "pretax_income", "gaap_pretax_income_loss",
)
REVENUE_METRICS = (
    "gaap_total_revenue", "gaap_net_revenue", "net_revenues", "gaap_revenue",
)
EXPENSE_METRICS = (
    "gaap_total_expense", "gaap_total_expenses", "gaap_total_operating_expenses",
    "gaap_total_noninterest_expense", "operating_expenses",
)
OPERATING_METRICS = ("gaap_operating_income", "operating_income")

LOWER_ABSOLUTE_TAX = re.compile(
    r"\btax\s+(?:expense|provision)\s+(?:fell|declined|decreased)\b",
    re.I,
)
HIGHER_ABSOLUTE_TAX = re.compile(
    r"\btax\s+(?:expense|provision)\s+(?:rose|increased)\b",
    re.I,
)
DENY_LOWER_TAX_RATE = re.compile(
    r"\b(?:effective\s+tax\s+rate|tax\s+rate)\s+"
    r"(?:did\s+not|does\s+not|has\s+not)\s+(?:fall|decline|decrease)\b|"
    r"\b(?:not|no)\s+(?:evidence\s+of\s+)?(?:a\s+)?"
    r"(?:reduced|lower|smaller)\s+(?:effective\s+tax\s+rate|tax\s+rate)\b|"
    r"\bafter-tax\s+(?:growth|result)\s+was\s+not\s+tax-assisted\b",
    re.I,
)
HIGHER_TAX_BURDEN = re.compile(
    r"\b(?:higher|larger|increased)\s+(?:effective\s+tax\s+rate|tax\s+rate)\b",
    re.I,
)
EXPENSE_EXCEEDS_REVENUE = re.compile(
    r"\b(?:total\s+)?expenses?\s+(?:grew|rose|increased)\s+by\s+more\s+than\s+"
    r"(?:total\s+)?(?:net\s+)?revenues?\b|"
    r"\brevenue\s+increase\s+was\s+accompanied\s+by\s+a\s+larger\s+"
    r"increase\s+in\s+total\s+expense\b",
    re.I,
)
OPERATING_EXCEEDS_REVENUE = re.compile(
    r"\boperating(?:\s+and\s+pretax)?\s+(?:income|profit)\s+"
    r"(?:rose|grew|increased)\s+by\s+more\s+than\s+revenue\b|"
    r"\boperating\s+income\s+and\s+pretax\s+income\s+"
    r"(?:rose|grew|increased)\s+by\s+more\s+than\s+revenue\b",
    re.I,
)


def _row(rows: dict, names: tuple[str, ...]) -> dict | None:
    for name in names:
        value = rows.get("SEQ:" + name)
        if isinstance(value, dict):
            return value
    return None


def _number(row: dict | None, key: str) -> Decimal | None:
    try:
        return Decimal(str(row[key])) if row else None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def _claims(candidate: dict, state: dict) -> str:
    interpretation = candidate.get("interpretation") or {}
    text = " ".join(str(interpretation.get(key) or "") for key in
                    ("implication", "counterevidence")) if isinstance(
                        interpretation, dict) else ""
    theses = state.get("theses") or [] if isinstance(state, dict) else []
    if len(theses) == 1:
        reviews = theses[0].get("reviews") or []
        if len(reviews) == 1:
            text += " " + str(reviews[0].get("rationale") or "")
    return text


def screen(catalog: dict, candidate: dict, state: dict) -> dict:
    """Return conservative alerts; an empty list does not imply correctness."""
    baseline = v2_screen(catalog, candidate, state)
    # V2 conflates absolute tax expense and effective-rate burden. Preserve
    # its unrelated flags, then adjudicate tax language on matching bases.
    alerts = [item for item in baseline["alerts"]
              if item != "tax_direction_contradiction"]
    if not isinstance(candidate, dict):
        return {"alerts": alerts, "quality_pass": None}
    rows = catalog.get("rows") or {}
    text = _claims(candidate, state)
    tax, pretax = _row(rows, TAX_METRICS), _row(rows, PRETAX_METRICS)
    tax_change = _number(tax, "delta_value")
    if tax_change is not None:
        if tax_change > 0 and LOWER_ABSOLUTE_TAX.search(text):
            alerts.append("absolute_tax_expense_direction_contradiction")
        if tax_change < 0 and HIGHER_ABSOLUTE_TAX.search(text):
            alerts.append("absolute_tax_expense_direction_contradiction")
    tax_before, tax_after = _number(tax, "baseline_value"), _number(tax, "event_value")
    pretax_before, pretax_after = (_number(pretax, "baseline_value"),
                                  _number(pretax, "event_value"))
    if (None not in (tax_before, tax_after, pretax_before, pretax_after)
            and pretax_before > 0 and pretax_after > 0):
        rate_before = tax_before / pretax_before
        rate_after = tax_after / pretax_after
        # Allow 10 basis points for display rounding. Generic "tax burden"
        # language can mean absolute expense and is deliberately not flagged.
        # Never infer a tax-rate conclusion from loss-period effective rates.
        if rate_before - rate_after > Decimal("0.001") and (
                DENY_LOWER_TAX_RATE.search(text) or HIGHER_TAX_BURDEN.search(text)):
            alerts.append("effective_tax_rate_decline_denied")

    revenue = _row(rows, REVENUE_METRICS)
    expense = _row(rows, EXPENSE_METRICS)
    operating = _row(rows, OPERATING_METRICS)
    revenue_change = _number(revenue, "delta_value")
    expense_change = _number(expense, "delta_value")
    operating_change = _number(operating, "delta_value")
    if (revenue_change is not None and expense_change is not None
            and expense_change <= revenue_change
            and EXPENSE_EXCEEDS_REVENUE.search(text)):
        alerts.append("expense_revenue_increment_reversed")
    if (revenue_change is not None and operating_change is not None
            and operating_change <= revenue_change
            and OPERATING_EXCEEDS_REVENUE.search(text)):
        alerts.append("operating_revenue_increment_reversed")
    return {"alerts": list(dict.fromkeys(alerts)), "quality_pass": None}
