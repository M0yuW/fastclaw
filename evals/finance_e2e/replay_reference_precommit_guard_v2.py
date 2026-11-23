#!/usr/bin/env python3
"""Free direct-plugin A/B for newly identified review defects.

This is a developmental replay of saved model calls on isolated ledgers, not
a fresh model test or a claim that the proposed guard generalizes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_reference_source_distinct_event_fixtures_v1 import preflight
from replay_reference_precommit_guard_v1 import JUDGMENTS, review_call, run_arm
from run_thesis_event_gateway import load_plugin


CASES = {
    "J-b6e559adea6c6abb": ("BOKF", "claimed_hold_not_in_ledger"),
    "J-bf4eba69527e01ab": ("TOST", "signed_tax_contribution_reversed"),
    "J-12d921bb4b32208c": ("MQ", None),
    "J-d9ea0e54a3a5b5f4": ("EFX", None),
}


def run() -> dict:
    fixtures = {item["runtime_symbol"]: item for item in preflight()["fixtures"]}
    plugin_class = load_plugin().FinanceToolsPlugin
    cases = []
    with tempfile.TemporaryDirectory(prefix="reference-precommit-ab-v2-") as temp:
        root = Path(temp)
        for masked_id, (symbol, expected_alert) in CASES.items():
            packet = json.loads((JUDGMENTS / "masked_packets" /
                                 f"{masked_id}.json").read_text())
            if packet["source_packet"]["symbol"] != symbol:
                raise ValueError("masked source symbol changed")
            original = review_call(packet)
            fixture = fixtures[symbol]
            case_root = root / masked_id
            case_root.mkdir()
            a = run_arm(plugin_class, fixture, original, "A", case_root)
            b = run_arm(plugin_class, fixture, original, "B", case_root)
            checks = {
                "same_model_proposal": a["original_model_decision"] ==
                    b["original_model_decision"] == original["decision"],
                "one_linked_review_each": a["saved_review_count"] ==
                    b["saved_review_count"] == 1 and a["alert_id_linked"]
                    and b["alert_id_linked"],
                "status_conviction_preserved": a["status"] == b["status"] ==
                    "active" and a["conviction"] == b["conviction"] == 3,
            }
            if expected_alert:
                checks.update({
                    "baseline_actionable": a["actionability"] == "available"
                        and not a["decision_hold"],
                    "guard_vetoed_before_write": b["precommit_veto"]
                        and b["pre_fallback_review_count"] == 0
                        and b["review_error_code"] ==
                            "review_arithmetic_contradiction"
                        and expected_alert in b["veto_alerts"],
                    "fallback_blocked": b["saved_review_decision"] ==
                        "needs_review" and b["actionability"] == "blocked"
                        and b["decision_hold"],
                })
            else:
                checks.update({
                    "already_held": a["actionability"] ==
                        b["actionability"] == "blocked" and a["decision_hold"]
                        and b["decision_hold"],
                    "no_guard_veto": not b["precommit_veto"],
                })
                if symbol == "EFX":
                    checks["incorrect_prose_sanitized_without_losing_hold"] = (
                        a["saved_rationale_matches_original"]
                        and not b["saved_rationale_matches_original"]
                        and b["saved_rationale_guard_sanitized"])
                else:
                    checks["good_control_rationale_preserved"] = (
                        a["saved_rationale_matches_original"]
                        and b["saved_rationale_matches_original"]
                        and not b["saved_rationale_guard_sanitized"])
            if not all(checks.values()):
                raise AssertionError(f"direct-plugin A/B failed for {symbol}: {checks}")
            cases.append({"masked_id": masked_id, "symbol": symbol,
                          "expected_alert": expected_alert, "checks": checks,
                          "A": a, "B": b})
    return {"study_type": "developmental_direct_plugin_precommit_ab_v2",
            "model_calls": 0, "gateway_calls": 0, "external_cost_usd": 0,
            "generalization_claim": False, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
