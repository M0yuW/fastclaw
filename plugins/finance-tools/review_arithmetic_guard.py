"""Optional source-bound arithmetic veto before a research review is saved.

The catalog is supplied by the trusted host, not by a model tool argument.
An unrecognised source pair fails closed when this experimental guard is on.
Only explicit, mechanically decidable claims are checked; an empty alert list
does not imply that the rest of the financial interpretation is correct.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path


HEX64 = re.compile(r"^[0-9a-f]{64}$")
OPERATING_EXCEEDS_REVENUE = re.compile(
    r"\boperating(?:\s+and\s+pretax)?\s+(?:income|profit)\s+"
    r"(?:rose|grew|increased)\s+by\s+more\s+than\s+revenue\b|"
    r"\boperating\s+income\s+and\s+pretax\s+income\s+"
    r"(?:rose|grew|increased)\s+by\s+more\s+than\s+revenue\b",
    re.I,
)
EXPENSE_EXCEEDS_REVENUE = re.compile(
    r"\b(?:total\s+)?expenses?\s+(?:grew|rose|increased)\s+by\s+more\s+than\s+"
    r"(?:total\s+)?(?:net\s+)?revenues?\b|"
    r"\brevenue\s+increase\s+was\s+accompanied\s+by\s+a\s+larger\s+"
    r"increase\s+in\s+total\s+expense\b",
    re.I,
)
TAX_DRAG_REVERSED = re.compile(
    r"\b(?:tax\s+(?:provision|expense|line|charge)|signed\s+income\s+tax\s+line)\b"
    r"[^.]{0,100}\b(?:larger\s+(?:provision|tax\s+charge)|"
    r"larger\s+tax\s+drag)\b",
    re.I,
)
TAX_DRAG_NEGATED = re.compile(r"\b(?:not|no|never)\b[^.]{0,30}\blarger\b", re.I)
RESEARCH_HOLD_PRESERVED = re.compile(
    r"\b(?:research|decision)\s+hold\s+(?:is\s+)?preserved\b|"
    r"\bthesis\s+remains\s+(?:on\s+)?hold\b",
    re.I,
)
REVENUE_NAMES = ("gaap_total_revenue", "gaap_net_revenue", "gaap_revenue")
OPERATING_NAMES = ("gaap_operating_income", "gaap_operating_income_loss",
                   "gaap_operating_loss", "operating_income")
EXPENSE_NAMES = ("gaap_total_expense", "gaap_total_expenses",
                 "gaap_total_operating_expenses", "operating_expenses")
TAX_NAMES = ("gaap_income_tax_expense_benefit", "gaap_income_tax_benefit",
             "gaap_income_tax_provision")


class GuardCatalogError(ValueError):
    pass


def _hashes(value: object) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item.get("sha256", "") for item in value if isinstance(item, dict)
            and isinstance(item.get("sha256"), str)}


def _row(rows: dict, names: tuple[str, ...]) -> dict | None:
    for name in names:
        value = rows.get("SEQ:" + name)
        if isinstance(value, dict):
            return value
    return None


def _delta(row: dict | None) -> Decimal | None:
    try:
        return Decimal(str(row["delta_value"])) if row else None
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


class ReviewArithmeticGuard:
    def __init__(self, path: Path) -> None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise GuardCatalogError("review arithmetic guard catalog cannot be read") from exc
        if not isinstance(data, dict) or data.get("version") != "review-arithmetic-guard-catalog-v1":
            raise GuardCatalogError("review arithmetic guard catalog version is invalid")
        cases = data.get("cases")
        if not isinstance(cases, list) or not cases or len(cases) > 100:
            raise GuardCatalogError("review arithmetic guard cases must contain 1-100 entries")
        self.cases = {}
        for case in cases:
            if not isinstance(case, dict) or not isinstance(case.get("rows"), dict):
                raise GuardCatalogError("review arithmetic guard case is malformed")
            symbol = case.get("symbol")
            baseline_hash = case.get("baseline_source_sha256")
            event_hash = case.get("event_source_sha256")
            if (not isinstance(symbol, str) or not symbol
                    or not isinstance(baseline_hash, str) or not HEX64.fullmatch(baseline_hash)
                    or not isinstance(event_hash, str) or not HEX64.fullmatch(event_hash)):
                raise GuardCatalogError("review arithmetic guard source identity is invalid")
            key = (symbol.upper(), baseline_hash, event_hash)
            if key in self.cases:
                raise GuardCatalogError("duplicate review arithmetic guard source pair")
            self.cases[key] = case["rows"]

    def check(self, thesis: dict, event: dict, rationale: str,
              decision: str | None = None) -> list[str]:
        symbol = str(thesis.get("symbol") or "").upper()
        baseline_hashes = _hashes(thesis.get("evidence"))
        event_hashes = _hashes(event.get("sources"))
        matches = [rows for (case_symbol, before_hash, after_hash), rows
                   in self.cases.items()
                   if case_symbol == symbol and before_hash in baseline_hashes
                   and after_hash in event_hashes]
        if len(matches) != 1:
            raise GuardCatalogError("no unique trusted comparison for stored thesis and alert")
        rows = matches[0]
        revenue = _row(rows, REVENUE_NAMES)
        operating = _row(rows, OPERATING_NAMES)
        expense = _row(rows, EXPENSE_NAMES)
        alerts = []
        rev_delta, op_delta, exp_delta = _delta(revenue), _delta(operating), _delta(expense)
        if (rev_delta is not None and op_delta is not None and op_delta <= rev_delta
                and revenue.get("unit") == operating.get("unit")
                and OPERATING_EXCEEDS_REVENUE.search(rationale)):
            alerts.append("operating_revenue_increment_reversed")
        if (rev_delta is not None and exp_delta is not None and exp_delta <= rev_delta
                and revenue.get("unit") == expense.get("unit")
                and EXPENSE_EXCEEDS_REVENUE.search(rationale)):
            alerts.append("expense_revenue_increment_reversed")
        tax = _row(rows, TAX_NAMES)
        tax_delta = _delta(tax)
        tax_basis = str(tax.get("basis", "")) if tax else ""
        tax_line_improved = tax_delta is not None and (
            ("signed_contribution" in tax_basis and tax_delta > 0)
            or (("signed_expense" in tax_basis or "signed_tax_expense" in tax_basis)
                and tax_delta < 0))
        if (tax_line_improved
                and any(not TAX_DRAG_NEGATED.search(match.group())
                        for match in TAX_DRAG_REVERSED.finditer(rationale))):
            alerts.append("signed_tax_contribution_reversed")
        if (decision is not None and decision != "needs_review"
                and not thesis.get("decision_hold")
                and RESEARCH_HOLD_PRESERVED.search(rationale)):
            alerts.append("claimed_hold_not_in_ledger")
        return alerts
