#!/usr/bin/env python3
"""Read-only scope check for the opt-in, post-hoc precommit guard v2."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import validate_review
from audit_reference_precommit_guard_offline_v1 import (
    JUDGMENTS, audit as verify_prior_audit, guard_catalog, load_guard_class,
)
from build_reference_source_distinct_event_fixtures_v1 import preflight


HERE = Path(__file__).resolve().parent
MINI_REVIEWS = (HERE / "results" /
                "2026-10-27-reference-mini-qualitative-selection-v1" / "reviews")


def audit() -> dict:
    prior = verify_prior_audit()  # Verifies frozen raw hashes and all masked packets.
    mapping = json.loads((JUDGMENTS / "PRIVATE-MAPPING.json").read_text())
    ReviewArithmeticGuard, GuardCatalogError = load_guard_class()
    with tempfile.TemporaryDirectory(prefix="reference-guard-scope-v2-") as temp:
        catalog_path = Path(temp) / "catalog.json"
        catalog_path.write_text(json.dumps(guard_catalog(preflight()["fixtures"])))
        guard = ReviewArithmeticGuard(catalog_path)
        counts = Counter()
        flagged = []
        for entry in mapping:
            mask = entry["masked_id"]
            packet = json.loads((JUDGMENTS / "masked_packets" /
                                 f"{mask}.json").read_text())
            theses = packet.get("persisted_theses_and_reviews") or []
            alerts = packet.get("persisted_alerts") or []
            if len(theses) != 1 or len(theses[0].get("reviews") or []) != 1 or len(alerts) != 1:
                counts["not_unique"] += 1
                continue
            thesis, review, event = (theses[0]["thesis"],
                                     theses[0]["reviews"][0], alerts[0]["event"])
            decision = review["decision"]
            try:
                flags = guard.check(thesis, event, review["rationale"], decision)
            except GuardCatalogError:
                counts["source_mismatch"] += 1
                continue
            counts["checked"] += 1
            if not flags:
                continue
            counts["flagged"] += 1
            if decision != "needs_review":
                counts["would_veto_original_write"] += 1
            mini_path = MINI_REVIEWS / f"{mask}.json"
            mini_label = (validate_review(json.loads(mini_path.read_text()), mask)
                          if mini_path.exists() else None)
            flagged.append({
                "masked_id": mask,
                "observation_id": entry["observation_id"],
                "symbol": packet["source_packet"]["symbol"],
                "original_decision": decision,
                "original_actionability": thesis.get("actionability"),
                "flags": flags,
                "would_veto_original_write": decision != "needs_review",
                "mini_diagnostic_label": mini_label,
            })
    flagged.sort(key=lambda item: item["observation_id"])
    if counts["checked"] != prior["saved_model_observations"]:
        raise AssertionError("the v2 guard did not cover all archived observations")
    return {
        "study_type": "post_hoc_archival_guard_scope_v2",
        "verified_saved_observations": prior["saved_model_observations"],
        "source_issuer_cases": prior["source_issuer_cases"],
        "model_calls": 0, "gateway_calls": 0, "external_cost_usd": 0,
        "counts": dict(sorted(counts.items())),
        "flagged": flagged,
        "interpretation_boundary": (
            "Rules were added after seeing some saved errors. Flags are potential "
            "precommit vetoes on archived rationales, not observed model recovery, "
            "prospective sensitivity, specificity, or an overall quality rate. "
            "A needs_review write is already non-actionable. The current "
            "opt-in plugin hook would preserve that hold but replace a "
            "flagged rationale with a neutral warning; archived original "
            "reviews remain unchanged."
        ),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), ensure_ascii=False, indent=2))
