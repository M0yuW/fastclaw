#!/usr/bin/env python3
"""Free developmental A/B at the finance tool's pre-commit boundary.

The identical saved model review call is replayed on isolated plugin ledgers.
B either forwards it unchanged or vetoes it and records a deterministic
needs_review hold. This is a direct plugin replay, not a Gateway replay, and
the rule was developed after inspecting some of these answers.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_thesis_event_gateway import load_plugin, must_call


HERE = Path(__file__).resolve().parent
JUDGMENTS = (HERE / "results" /
             "2026-10-26-reference-source-distinct-insight-judgment-v1")
CASES = ("J-a43fcf41e603f011", "J-12d921bb4b32208c")


def review_call(packet: dict) -> dict:
    calls = [json.loads(item["arguments"])
             for item in packet["tool_evidence"]
             if item.get("type") == "tool_call"
             and item.get("name") == "finance-tools__thesis_record_review"]
    if len(calls) != 1:
        raise ValueError("expected exactly one recorded review call")
    return calls[0]


def run_arm(plugin_class, fixture: dict, original: dict,
            branch: str, root: Path) -> dict:
    catalog_path = root / "guard-catalog.json"
    catalog = fixture["catalog"]
    catalog_path.write_text(json.dumps({
        "version": "review-arithmetic-guard-catalog-v1",
        "cases": [{
            "symbol": fixture["runtime_symbol"],
            "baseline_source_sha256": catalog["baseline"]["source_sha256"],
            "event_source_sha256": catalog["event"]["source_sha256"],
            "rows": catalog["rows"],
        }],
    }))
    plugin = plugin_class()
    config = {"stateDbPath": str(root / f"{branch}.db")}
    if branch == "B":
        config["reviewArithmeticGuardCatalogPath"] = str(catalog_path)
    plugin.initialize(config)
    tenant = {"userId": f"replay-{branch}", "agentId": "finance-coordinator",
              "sessionId": f"reference-precommit-{branch}"}
    symbol = fixture["runtime_symbol"]
    thesis = must_call(plugin, "thesis_save", fixture["seed_thesis"], tenant)["thesis"]
    must_call(plugin, "watchlist_save", {
        "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [symbol],
        "min_match_score": 1,
    }, tenant)
    alert = must_call(plugin, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": fixture["event"],
    }, tenant)["results"][0]["alert"]
    arguments = {**original, "thesis_id": thesis["id"],
                 "alert_id": alert["id"], "expected_version": thesis["version"]}
    alerts = []
    veto = False
    review_error_code = None
    pre_fallback_review_count = None
    if branch == "B":
        attempted = plugin.execute("thesis_record_review", arguments, tenant)
        if attempted["ok"]:
            saved = attempted["data"]
        else:
            review_error_code = attempted["errors"][0]["code"]
            if review_error_code != "review_arithmetic_contradiction":
                raise RuntimeError(f"unexpected guard error: {attempted['errors']}")
            veto = True
            alerts = attempted["errors"][0].get("details", {}).get("alerts", [])
            pre_fallback_review_count = len(must_call(
                plugin, "thesis_get", {"thesis_id": thesis["id"]}, tenant)["reviews"])
            arguments = {
                "thesis_id": thesis["id"], "alert_id": alert["id"],
                "expected_version": thesis["version"],
                "event": {"summary": alert["event"]["summary"]},
                "impact": "mixed", "decision": "needs_review",
                "rationale": "Pre-commit arithmetic check found a contradiction in the proposed "
                             "review rationale; preserve the thesis and verify the "
                             "source comparison before downstream decision use.",
                "evidence": [fixture["seed_thesis"]["evidence"][0],
                             fixture["event"]["sources"][0]],
                "causal_claims": [],
            }
            saved = must_call(plugin, "thesis_record_review", arguments, tenant)
    else:
        saved = must_call(plugin, "thesis_record_review", arguments, tenant)
    detail = must_call(plugin, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
    saved_rationale = detail["reviews"][0]["rationale"]
    return {
        "branch": branch,
        "original_model_decision": original["decision"],
        "precommit_veto": veto,
        "review_error_code": review_error_code,
        "pre_fallback_review_count": pre_fallback_review_count,
        "veto_alerts": alerts,
        "saved_review_decision": detail["reviews"][0]["decision"],
        "saved_rationale_matches_original": saved_rationale == original["rationale"],
        "saved_rationale_guard_sanitized": saved_rationale.startswith(
            "Source-bound review check flagged "),
        "saved_review_count": len(detail["reviews"]),
        "status": detail["thesis"]["status"],
        "conviction": detail["thesis"]["conviction"],
        "decision_hold": detail["thesis"]["decision_hold"],
        "actionability": detail["thesis"]["actionability"],
        "alert_id_linked": detail["reviews"][0]["alert_id"] == alert["id"],
        "tool_returned_same_thesis": saved["thesis"]["id"] == thesis["id"],
    }


def run() -> dict:
    fixtures = {item["runtime_symbol"]: item for item in preflight()["fixtures"]}
    plugin_class = load_plugin().FinanceToolsPlugin
    cases = []
    with tempfile.TemporaryDirectory(prefix="reference-precommit-ab-") as temp:
        root = Path(temp)
        for masked_id in CASES:
            packet = json.loads((JUDGMENTS / "masked_packets" /
                                 f"{masked_id}.json").read_text())
            symbol = packet["source_packet"]["symbol"]
            original = review_call(packet)
            fixture = fixtures[symbol]
            (root / masked_id).mkdir()
            a = run_arm(plugin_class, fixture, original, "A",
                        root / masked_id)
            b = run_arm(plugin_class, fixture, original, "B",
                        root / masked_id)
            if symbol == "JKHY":
                checks = {
                    "same_original_model_decision":
                        a["original_model_decision"] == b["original_model_decision"] == "maintain",
                    "baseline_available": a["actionability"] == "available"
                        and not a["decision_hold"],
                    "guard_vetoed_arithmetic_error": b["precommit_veto"]
                        and "operating_revenue_increment_reversed" in b["veto_alerts"],
                    "guard_blocked_before_decision_use": b["actionability"] == "blocked"
                        and b["decision_hold"] and b["saved_review_decision"] == "needs_review",
                    "status_and_conviction_unchanged":
                        a["status"] == b["status"] == "active"
                        and a["conviction"] == b["conviction"] == 3,
                }
            else:
                checks = {
                    "same_original_model_decision":
                        a["original_model_decision"] == b["original_model_decision"] == "needs_review",
                    "good_control_not_vetoed": not b["precommit_veto"],
                    "both_correctly_blocked":
                        a["actionability"] == b["actionability"] == "blocked"
                        and a["decision_hold"] and b["decision_hold"],
                    "status_and_conviction_unchanged":
                        a["status"] == b["status"] == "active"
                        and a["conviction"] == b["conviction"] == 3,
                }
            checks["one_linked_review_each"] = (
                a["saved_review_count"] == b["saved_review_count"] == 1
                and a["alert_id_linked"] and b["alert_id_linked"])
            if not all(checks.values()):
                raise AssertionError(f"pre-commit replay failed for {masked_id}: {checks}")
            cases.append({"masked_id": masked_id, "symbol": symbol,
                          "checks": checks, "A": a, "B": b})
    return {"study_type": "developmental_direct_plugin_precommit_ab",
            "gateway_calls": 0, "model_calls": 0, "external_cost_usd": 0,
            "quality_pass": None, "cases": cases}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
