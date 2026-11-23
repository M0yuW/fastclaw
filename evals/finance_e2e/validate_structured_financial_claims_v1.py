#!/usr/bin/env python3
"""Validate explicit numeric claim records against source-audited period rows.

This is a development component for a *future* publication gate. It verifies
only submitted structured claims, not whether prose contains omitted or
unsupported claims, and never assigns an insight-quality score.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation


RATE_TOLERANCE_PERCENTAGE_POINTS = Decimal("0.05")


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    try:
        number = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("claim value is not decimal") from exc
    if not number.is_finite():
        raise ValueError("claim value is not finite")
    return number


def _row(facts: dict, role: str, metric: str) -> dict:
    if role not in ("baseline", "event"):
        raise ValueError("invalid period role")
    row = facts.get(role, {}).get(metric)
    if not isinstance(row, dict) or not all(k in row for k in ("value", "unit", "basis")):
        raise ValueError(f"missing typed source row: {role}.{metric}")
    return row


def _same_metric(facts: dict, metric: str) -> tuple[Decimal, Decimal, str, str]:
    before, after = _row(facts, "baseline", metric), _row(facts, "event", metric)
    if (before["unit"], before["basis"]) != (after["unit"], after["basis"]):
        raise ValueError(f"period unit/basis mismatch: {metric}")
    return _decimal(before["value"]), _decimal(after["value"]), before["unit"], before["basis"]


def _delta(facts: dict, metric: str) -> tuple[Decimal, str, str]:
    before, after, unit, basis = _same_metric(facts, metric)
    return after - before, unit, basis


def _relation(actual: Decimal, expected: str) -> bool:
    if expected not in ("gt", "lt", "eq"):
        raise ValueError("invalid relation")
    return {"gt": actual > 0, "lt": actual < 0, "eq": actual == 0}[expected]


def _comparison_mode_and_reported_pair(claim: dict, left: Decimal,
                                       right: Decimal) -> bool:
    """Validate any model-supplied delta pair before using its comparison.

    A literal true requests absolute-value comparison. Historical development
    answers also supplied signed delta pairs as arrays or keyed objects; they
    must match the source-derived deltas exactly, never be silently ignored.
    """
    reported = claim.get("magnitudes", False)
    if isinstance(reported, bool):
        return reported
    if isinstance(reported, list) and len(reported) == 2:
        pair = reported
    elif isinstance(reported, dict):
        metric_keys = {claim["left_metric"], claim["right_metric"]}
        if len(metric_keys) == 2 and set(reported) == metric_keys:
            pair = [reported[claim["left_metric"]], reported[claim["right_metric"]]]
        elif set(reported) == {"left", "right"}:
            pair = [reported["left"], reported["right"]]
        else:
            raise ValueError("reported delta pair keys do not identify both metrics")
    else:
        raise ValueError("magnitudes must be boolean or a two-delta report")
    if [_decimal(value) for value in pair] != [left, right]:
        raise ValueError("reported delta pair differs from selected source rows")
    return False


def validate_claim(facts: dict, claim: dict) -> dict:
    """Return a conservative verdict for one typed numeric assertion."""
    try:
        if not isinstance(claim, dict):
            raise ValueError("claim must be an object")
        op = claim.get("op")
        if op == "delta":
            actual, unit, basis = _delta(facts, claim["metric"])
            if claim.get("unit") != unit or claim.get("basis") != basis:
                raise ValueError("claim unit/basis differs from selected source row")
            correct = _decimal(claim["value"]) == actual
            expected = str(actual)
        elif op == "compare_delta":
            left, left_unit, left_basis = _delta(facts, claim["left_metric"])
            right, right_unit, right_basis = _delta(facts, claim["right_metric"])
            if left_unit != right_unit:
                raise ValueError("comparison mixes units")
            if left_basis != right_basis and not claim.get("cross_basis_explicit"):
                raise ValueError("comparison mixes basis without explicit label")
            compare_absolute = _comparison_mode_and_reported_pair(claim, left, right)
            compared = abs(left) - abs(right) if compare_absolute else left - right
            correct = _relation(compared, claim.get("relation"))
            expected = ("gt" if compared > 0 else "lt" if compared < 0 else "eq")
        elif op == "ratio_direction":
            numerator = claim["numerator_metric"]
            denominator = claim["denominator_metric"]
            num_before, num_after, num_unit, num_basis = _same_metric(facts, numerator)
            den_before, den_after, den_unit, den_basis = _same_metric(facts, denominator)
            if num_unit != den_unit or den_before == 0 or den_after == 0:
                raise ValueError("ratio unit/denominator invalid")
            if num_basis != den_basis and not claim.get("cross_basis_explicit"):
                raise ValueError("ratio mixes basis without explicit label")
            compared = num_after / den_after - num_before / den_before
            correct = _relation(compared, claim.get("relation"))
            expected = ("gt" if compared > 0 else "lt" if compared < 0 else "eq")
        elif op == "delta_share_percent":
            numerator, num_unit, _ = _delta(facts, claim["numerator_metric"])
            denominator, den_unit, _ = _delta(facts, claim["denominator_metric"])
            if num_unit != den_unit or denominator == 0:
                raise ValueError("share unit/denominator invalid")
            actual = abs(numerator / denominator) * 100
            correct = abs(_decimal(claim["value"]) - actual) <= RATE_TOLERANCE_PERCENTAGE_POINTS
            expected = str(actual)
        elif op == "gap_direction":
            left_before, left_after, left_unit, left_basis = _same_metric(facts, claim["left_metric"])
            right_before, right_after, right_unit, right_basis = _same_metric(facts, claim["right_metric"])
            if left_unit != right_unit:
                raise ValueError("gap mixes units")
            if left_basis != right_basis and not claim.get("cross_basis_explicit"):
                raise ValueError("gap mixes basis without explicit label")
            compared = abs(left_after - right_after) - abs(left_before - right_before)
            correct = _relation(compared, claim.get("relation"))
            expected = ("gt" if compared > 0 else "lt" if compared < 0 else "eq")
        elif op == "signed_delta_identity":
            total, unit, _ = _delta(facts, claim["total_metric"])
            terms = claim["terms"]
            if not isinstance(terms, list) or not terms:
                raise ValueError("signed identity requires terms")
            contribution = Decimal(0)
            for term in terms:
                part, part_unit, _ = _delta(facts, term["metric"])
                if part_unit != unit or term.get("sign") not in (-1, 1):
                    raise ValueError("signed identity term unit/sign invalid")
                contribution += part * term["sign"]
            correct = contribution == total and _decimal(claim["value"]) == total
            expected = str(total)
        else:
            raise ValueError("unsupported claim operation")
        return {"status": "verified" if correct else "contradicted",
                "op": op, "expected": expected}
    except (KeyError, TypeError, ValueError) as exc:
        return {"status": "invalid_or_unassessable", "op": claim.get("op") if isinstance(claim, dict) else None,
                "error": str(exc)}


def validate_claims(facts: dict, claims: list[dict]) -> dict:
    if not isinstance(claims, list) or not claims:
        return {"status": "no_coverage", "items": [], "quality_pass": None}
    items = [validate_claim(facts, claim) for claim in claims]
    return {"status": ("all_submitted_claims_verified" if all(
                item["status"] == "verified" for item in items) else "held_for_review"),
            "items": items, "quality_pass": None}
