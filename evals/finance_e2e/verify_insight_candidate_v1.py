#!/usr/bin/env python3
"""Prepublication gate for typed research candidates and actual ledger state.

Only structured assertions are machine-checked. A passing gate yields a
candidate for claim-level qualitative review, never an automatic quality pass.
Free-form final prose from old runs cannot be retroactively certified here.
"""

from __future__ import annotations

import re

from validate_structured_financial_claims_v1 import validate_claims


REQUIRED_STATE_KEYS = {
    "review_id", "evidence_ids", "next_review_at", "decision_hold",
    "actionability", "alert_status",
}
UNSTRUCTURED_NUMBER = re.compile(r"\d|[$€¥%]|\b(?:USD|bps|basis points?)\b", re.I)


def canonical_state(state: dict) -> dict:
    theses = state.get("theses") or []
    alerts = state.get("alerts") or []
    if len(theses) != 1 or len(alerts) != 1:
        raise ValueError("exactly one thesis and alert required")
    thesis = theses[0].get("thesis") or {}
    reviews = theses[0].get("reviews") or []
    if len(reviews) != 1:
        raise ValueError("exactly one persisted review required")
    review = reviews[0]
    return {
        "review_id": review.get("id"),
        "evidence_ids": sorted(item.get("id") for item in review.get("evidence") or []),
        "next_review_at": thesis.get("next_review_at"),
        "decision_hold": thesis.get("decision_hold"),
        "actionability": thesis.get("actionability"),
        "alert_status": alerts[0].get("status"),
    }


def verify_candidate(facts: dict, candidate: dict, state: dict) -> dict:
    """Hold malformed/contradicted candidates; otherwise require further review."""
    issues = []
    if not isinstance(candidate, dict):
        return {"status": "held", "issues": ["candidate_not_object"],
                "quality_pass": None}
    if set(candidate) != {"claims", "interpretation", "asserted_state"}:
        issues.append("candidate_schema_mismatch")
    checked = validate_claims(facts, candidate.get("claims"))
    if checked["status"] != "all_submitted_claims_verified":
        issues.append("numeric_claims_unverified_or_uncovered")
    interpretation = candidate.get("interpretation")
    if (not isinstance(interpretation, dict)
            or set(interpretation) != {"implication", "counterevidence", "uncertainty"}
            or any(not isinstance(value, str) or not value.strip()
                   for value in interpretation.values())):
        issues.append("interpretation_incomplete")
    elif any(UNSTRUCTURED_NUMBER.search(value) for value in interpretation.values()):
        issues.append("unstructured_numeric_prose")
    theses = (state.get("theses") or []) if isinstance(state, dict) else []
    reviews = theses[0].get("reviews") or [] if len(theses) == 1 else []
    if len(reviews) == 1 and UNSTRUCTURED_NUMBER.search(reviews[0].get("rationale") or ""):
        issues.append("unstructured_numeric_saved_rationale")
    try:
        actual = canonical_state(state)
    except (ValueError, TypeError):
        actual = None
        issues.append("ledger_state_incomplete")
    asserted = candidate.get("asserted_state")
    if not isinstance(asserted, dict) or set(asserted) != REQUIRED_STATE_KEYS:
        issues.append("state_claim_schema_mismatch")
    elif actual is not None:
        asserted_ids = asserted.get("evidence_ids")
        if (not isinstance(asserted_ids, list)
                or any(not isinstance(item, str) for item in asserted_ids)):
            issues.append("state_claim_schema_mismatch")
        else:
            normalized_asserted = dict(asserted)
            normalized_asserted["evidence_ids"] = sorted(asserted_ids)
            if normalized_asserted != actual:
                issues.append("state_claim_contradicted_by_ledger")
    return {
        "status": "held" if issues else "candidate_for_qualitative_review",
        "issues": issues, "structured_claim_check": checked,
        "canonical_state": actual,
        "quality_pass": None,
    }


def render_review_card(facts: dict, candidate: dict, state: dict) -> dict:
    """Render only checked numeric results and canonical state for review.

    The model's interpretation is retained as an ungraded hypothesis. This is
    not a user-facing verified insight or a substitute for claim-level review.
    """
    gate = verify_candidate(facts, candidate, state)
    if gate["status"] != "candidate_for_qualitative_review":
        return {"status": "held", "issues": gate["issues"], "quality_pass": None}
    return {
        "status": "candidate_for_qualitative_review",
        "source_derived_assertions": [
            {"operation": claim["op"], "metric": claim.get("metric")
             or claim.get("total_metric") or claim.get("left_metric")
             or claim.get("numerator_metric"),
             "verified_result": checked["expected"]}
            for claim, checked in zip(candidate["claims"],
                                      gate["structured_claim_check"]["items"])
        ],
        "canonical_state": gate["canonical_state"],
        "interpretation_requires_review": candidate["interpretation"],
        "quality_pass": None,
    }
