#!/usr/bin/env python3
"""Gate reference-only research candidates; never award insight quality.

The model selects IDs from a complete host-derived SEC comparison catalog.
Only the host renders numeric values. Qualitative claims still need independent
claim-level review: an ID link is not proof that a causal inference follows.
"""

from __future__ import annotations

from verify_insight_candidate_v1 import (REQUIRED_STATE_KEYS,
                                         UNSTRUCTURED_NUMBER, canonical_state)


def verify_reference_candidate(catalog: dict, candidate: dict, state: dict) -> dict:
    issues = []
    if not isinstance(candidate, dict):
        return {"status": "held", "issues": ["candidate_not_object"],
                "quality_pass": None}
    if set(candidate) != {"selected_comparisons", "interpretation", "asserted_state"}:
        issues.append("candidate_schema_mismatch")
    selection = candidate.get("selected_comparisons")
    if not isinstance(selection, dict) or set(selection) != {"support", "counterevidence"}:
        issues.append("comparison_selection_schema_mismatch")
    else:
        known = set(catalog.get("rows") or {})
        for role in ("support", "counterevidence"):
            references = selection[role]
            if (not isinstance(references, list) or not references
                    or any(not isinstance(item, str) for item in references)
                    or len(references) != len(set(references))
                    or not set(references) <= known):
                issues.append(f"{role}_comparison_refs_invalid")
        if (all(isinstance(selection[role], list)
                and all(isinstance(item, str) for item in selection[role])
                for role in ("support", "counterevidence"))
                and set(selection["support"]) & set(selection["counterevidence"])):
            issues.append("support_counterevidence_refs_overlap")
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
        ids = asserted.get("evidence_ids")
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            issues.append("state_claim_schema_mismatch")
        elif {**asserted, "evidence_ids": sorted(ids)} != actual:
            issues.append("state_claim_contradicted_by_ledger")
    return {"status": "held" if issues else "candidate_for_qualitative_review",
            "issues": issues, "canonical_state": actual, "quality_pass": None}


def render_reference_card(catalog: dict, candidate: dict, state: dict) -> dict:
    gate = verify_reference_candidate(catalog, candidate, state)
    if gate["status"] == "held":
        return {"status": "held", "issues": gate["issues"], "quality_pass": None}
    return {
        "status": "candidate_for_qualitative_review",
        "source_scope": catalog["scope"],
        "period_comparison": catalog["comparison"],
        "sources": {role: catalog[role] for role in ("baseline", "event")},
        "selected_comparisons": candidate["selected_comparisons"],
        "complete_host_comparison_table": catalog["rows"],
        "canonical_state": gate["canonical_state"],
        "interpretation_requires_review": candidate["interpretation"],
        "quality_pass": None,
    }
