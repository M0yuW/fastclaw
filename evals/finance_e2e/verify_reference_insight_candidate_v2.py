#!/usr/bin/env python3
"""Prospective publication gate for reference-only insight candidates.

This layers conservative semantic red flags over the frozen v1 mechanical
gate. It does not change a persisted ledger review or certify financial
quality. Any alert holds the candidate for claim-level human review.
"""

from __future__ import annotations

from screen_reference_insight_semantics_v2 import screen
from verify_reference_insight_candidate_v1 import render_reference_card


def render_reference_card_v2(catalog: dict, candidate: dict, state: dict) -> dict:
    card = render_reference_card(catalog, candidate, state)
    semantic = screen(catalog, candidate, state)
    alerts = semantic["alerts"]
    if alerts:
        issues = list(card.get("issues") or [])
        issues.extend(alert for alert in alerts if alert not in issues)
        return {
            "status": "held",
            "issues": issues,
            "semantic_alerts": alerts,
            "quality_pass": None,
        }
    return {**card, "semantic_alerts": [], "quality_pass": None}
