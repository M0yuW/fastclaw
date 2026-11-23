#!/usr/bin/env python3
"""Development prompt contract for a future typed financial-insight arm.

No model result has yet validated autonomous compliance with this contract.
"""

from __future__ import annotations

import build_postcorrection_v4_event_preflight as source_batch


def candidate_prompt(fixture: dict, thesis_id: str, alert_id: str) -> str:
    return source_batch.review_prompt(fixture, thesis_id, alert_id) + (
        "\n\nOutput contract for this development workflow: after the finance-tool "
        "review and alert update, return exactly one JSON object and no Markdown. "
        "Do not let the output contract choose your financial implication or "
        "research-state decision. The JSON must have exactly three top-level keys: "
        "claims, interpretation, asserted_state.\n"
        "claims is a nonempty array of typed material quantitative assertions. "
        "Each assertion must use selected-source metric names and one supported op: "
        "delta(metric,value,unit,basis); compare_delta(left_metric,right_metric,"
        "relation gt|lt|eq,magnitudes optional,cross_basis_explicit optional); "
        "ratio_direction(numerator_metric,denominator_metric,relation); "
        "delta_share_percent(numerator_metric,denominator_metric,value); "
        "gap_direction(left_metric,right_metric,relation,cross_basis_explicit optional); "
        "or signed_delta_identity(total_metric,terms with metric and sign +1/-1,value). "
        "Include every material numerical, direction, rank, gap or proportional "
        "comparison you rely on. Omit unsupported assertions; a missing fact is "
        "a research limit, not a zero. Never infer economic causation from an "
        "accounting identity alone.\n"
        "interpretation has exactly implication, counterevidence and uncertainty, "
        "each a nonempty qualitative string. Do not put numbers, currency or "
        "percentages in these strings or the saved review rationale; quantitative "
        "claims belong in claims and the stored event facts. Explain your "
        "supported implication, the most material opposing evidence and what "
        "would be needed to resolve uncertainty.\n"
        "asserted_state has exactly review_id, evidence_ids, next_review_at, "
        "decision_hold, actionability and alert_status. Populate them from "
        "actual tool results and saved ledger state, not from intended tool "
        "arguments. If a review write fails, do not invent a review ID or claim "
        "the thesis is blocked; report the tool error instead of a completed "
        "candidate. Never trade or recommend a trade."
    )
