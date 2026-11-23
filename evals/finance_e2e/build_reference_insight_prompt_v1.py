#!/usr/bin/env python3
"""Development prompt for selecting host-verified SEC comparisons by ID."""

from __future__ import annotations

import build_postcorrection_v4_event_preflight as source_batch
from reference_insight_catalog_v1 import render_catalog


def reference_prompt(fixture: dict, catalog: dict, thesis_id: str,
                     alert_id: str) -> str:
    if fixture["case_id"] != catalog["case_id"]:
        raise ValueError("catalog and workflow case differ")
    return source_batch.review_prompt(fixture, thesis_id, alert_id) + (
        "\n\nReference-only conclusion contract: the complete source-derived "
        "comparison catalog below is authoritative for the selected displayed "
        "rows. Choose the comparisons material to your own interpretation; do "
        "not silently omit opposing evidence merely to pass validation. Return "
        "exactly one JSON object, without Markdown, with exactly three top-level "
        "keys: selected_comparisons, interpretation, asserted_state.\n"
        "selected_comparisons has exactly support and counterevidence, each a "
        "nonempty array of distinct comparison IDs from the catalog. The same "
        "ID cannot appear in both arrays. Interpret their economic meaning; "
        "an arithmetic contribution alone is not evidence of causation.\n"
        "interpretation has exactly implication, counterevidence and uncertainty, "
        "each a nonempty qualitative string. Do not recalculate or restate "
        "amounts, percentages, dates or ranked magnitudes in these strings or "
        "the saved review rationale. The host will render the complete numeric "
        "table, including rows you did not select. Discuss material limitations "
        "and what evidence would change the view.\n"
        "asserted_state has exactly review_id, evidence_ids, next_review_at, "
        "decision_hold, actionability and alert_status, copied from actual tool "
        "results and saved ledger state. If a review write fails, do not invent "
        "a completed review. Choose the research-state decision yourself, "
        "persist one linked review and acknowledge the alert. Do not trade.\n\n"
        + render_catalog(catalog)
    )
