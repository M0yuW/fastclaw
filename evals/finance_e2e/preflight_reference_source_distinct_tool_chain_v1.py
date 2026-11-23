#!/usr/bin/env python3
"""Free, isolated finance-tool replay for all 30 frozen SEC event fixtures.

This proves only that the source-bounded inputs and linked ledger operations
are accepted by the plugin. It does not exercise a model or grade insight.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from build_reference_source_distinct_event_fixtures_v1 import preflight
from build_reference_insight_prompt_v1 import reference_prompt
from run_thesis_event_gateway import load_plugin, must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, sha256


def replay_one(plugin_class, fixture: dict, root: Path) -> dict:
    symbol = fixture["runtime_symbol"]
    plugin = plugin_class()
    plugin.initialize({"stateDbPath": str(root / f"{symbol}.db")})
    tenant = {"userId": f"offline-{symbol}", "agentId": "finance-coordinator",
              "sessionId": "source-distinct-offline-preflight"}
    seed, event, catalog = (fixture[name] for name in
                            ("seed_thesis", "event", "catalog"))
    thesis = must_call(plugin, "thesis_save", seed, tenant)["thesis"]
    must_call(plugin, "watchlist_save", {
        "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [symbol], "min_match_score": 1,
    }, tenant)
    alert = must_call(plugin, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": event,
    }, tenant)["results"][0]["alert"]
    prompt = reference_prompt(fixture, catalog, thesis["id"], alert["id"])
    must_call(plugin, "thesis_record_review", {
        "thesis_id": thesis["id"], "alert_id": alert["id"],
        "expected_version": thesis["version"],
        "event": {"summary": alert["event"]["summary"]},
        "impact": "mixed", "decision": "needs_review",
        "rationale": "Selected source rows need further research before a decision is actionable.",
        "evidence": [seed["evidence"][0], event["sources"][0]],
        "next_review_at": "2027-01-31", "causal_claims": [],
    }, tenant)
    must_call(plugin, "alert_update", {
        "alert_id": alert["id"], "status": "acknowledged",
        "expected_version": alert["version"],
    }, tenant)
    detail = must_call(plugin, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
    alerts = must_call(plugin, "alert_list", {}, tenant)["alerts"]
    reviews = detail["reviews"]
    checks = {
        "one_linked_review": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"],
        "event_source_preserved": len(alerts) == 1
            and alerts[0]["event"]["sources"] == event["sources"],
        "event_metrics_preserved": len(alerts) == 1
            and alerts[0]["event"]["observed_metrics"] == event["observed_metrics"],
        "blocked_research_state": detail["thesis"]["actionability"] == "blocked"
            and detail["thesis"]["decision_hold"] is True,
        "alert_acknowledged": len(alerts) == 1
            and alerts[0]["status"] == "acknowledged",
        "references_delivered": all(identifier in prompt
                                    for identifier in catalog["rows"])
            and catalog["baseline"]["source_sha256"] in prompt
            and catalog["event"]["source_sha256"] in prompt,
        "nontrivial_comparison_choice": len(catalog["rows"]) >= 2,
    }
    return {"symbol": symbol, "case_id": fixture["case_id"],
            "comparison_rows": len(catalog["rows"]),
            "event_metrics": len(event["observed_metrics"]),
            "prompt_characters": len(prompt), "checks": checks,
            "all_checks_passed": all(checks.values())}


def run() -> dict:
    prepared = preflight()
    plugin_class = load_plugin().FinanceToolsPlugin
    with tempfile.TemporaryDirectory(prefix="source-distinct-tool-preflight-") as temp:
        cases = [replay_one(plugin_class, fixture, Path(temp))
                 for fixture in prepared["fixtures"]]
    return {
        "status": "offline_finance_tool_chain_preflight_no_model_calls",
        "source_freeze_sha256": prepared["source_freeze_sha256"],
        "run_order_sha256": prepared["run_order_sha256"],
        "case_count": len(cases),
        "passed_count": sum(case["all_checks_passed"] for case in cases),
        "model_observations": 0, "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
        "quality_pass": None, "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite")
    result = run()
    if result["case_count"] != 30 or result["passed_count"] != 30:
        raise AssertionError("not all 30 source-distinct tool chains passed")
    manifest = {"source_freeze_sha256": result["source_freeze_sha256"],
                "run_order_sha256": result["run_order_sha256"],
                "script_sha256": sha256(Path(__file__)),
                "plugin_sha256": sha256(PLUGIN_PATH),
                "fixture_builder_sha256": sha256(
                    HERE / "build_reference_source_distinct_event_fixtures_v1.py"),
                "prompt_builder_sha256": sha256(
                    HERE / "build_reference_insight_prompt_v1.py")}
    args.output_dir.mkdir(parents=True)
    for filename, data in (("RESULT.json", result), ("MANIFEST.json", manifest)):
        (args.output_dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps({key: value for key, value in result.items()
                      if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
