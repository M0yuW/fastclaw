#!/usr/bin/env python3
"""Free scripted Gateway replay of one frozen, source-distinct SEC case."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from build_reference_insight_prompt_v1 import reference_prompt
from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_finance_gateway_fault_replay import configure_provider, tool_stream
from run_finance_workflow_pilot import Pilot, start_gateway, stop_gateway
from run_insight_candidate_gateway_replay_v1 import DynamicCandidateProvider
from run_postcorrection_gateway_replay_v2 import gateway_turn
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, sha256
from verify_insight_candidate_v1 import canonical_state
from verify_reference_insight_candidate_v2 import render_reference_card_v2


def run(template_db: Path, binary: Path) -> dict:
    fixture = preflight()["fixtures"][0]
    catalog, seed, event = (fixture[key] for key in
                            ("catalog", "seed_thesis", "event"))
    symbol = fixture["runtime_symbol"]
    ids = list(catalog["rows"])
    if len(ids) < 2:
        raise ValueError("scripted citation branch needs two distinct IDs")
    with tempfile.TemporaryDirectory(prefix="source-distinct-gateway-replay-") as temp:
        pilot = Pilot("source-distinct-scripted-" + symbol,
                      template_db, binary, temp, False, 0.0)
        thesis = must_call(pilot.finance, "thesis_save", seed, pilot.tenant)["thesis"]
        must_call(pilot.finance, "watchlist_save", {
            "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": [symbol],
            "min_match_score": 1,
        }, pilot.tenant)
        alert = must_call(pilot.finance, "event_alert_ingest", {
            "market": "US", "symbol": symbol, "event": event,
        }, pilot.tenant)["results"][0]["alert"]
        calls = [
            tool_stream("read-thesis", "finance-tools__thesis_get",
                        {"thesis_id": thesis["id"]}),
            tool_stream("read-alert", "finance-tools__alert_list", {}),
            tool_stream("save-review", "finance-tools__thesis_record_review", {
                "thesis_id": thesis["id"], "alert_id": alert["id"],
                "expected_version": thesis["version"],
                "event": {"summary": alert["event"]["summary"]},
                "impact": "mixed", "decision": "needs_review",
                "rationale": "Selected source rows require a bounded follow-up before use.",
                "evidence": [seed["evidence"][0], event["sources"][0]],
                "next_review_at": "2027-01-31", "causal_claims": [],
            }),
            tool_stream("ack-alert", "finance-tools__alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"],
            }),
        ]

        def final_candidate() -> dict:
            return {
                "selected_comparisons": {
                    "support": [ids[0]], "counterevidence": [ids[1]]},
                "interpretation": {
                    "implication": "Selected evidence motivates a bounded research review.",
                    "counterevidence": "Other selected evidence limits the conclusion.",
                    "uncertainty": "The full business drivers require more source review.",
                },
                "asserted_state": canonical_state(pilot.ledger_state()),
            }

        with DynamicCandidateProvider(calls, final_candidate) as provider:
            configure_provider(pilot.home, provider.url)
            process, log = start_gateway(pilot.home)
            try:
                response = gateway_turn(pilot, reference_prompt(
                    fixture, catalog, thesis["id"], alert["id"]), symbol)
            finally:
                stop_gateway(process, log)
            provider_requests = provider.requests
        state = pilot.ledger_state()
    candidate = json.loads(response["choices"][0]["message"]["content"])
    card = render_reference_card_v2(catalog, candidate, state)
    trace = response.get("fastclaw", {}).get("trace", [])
    tool_calls = [item for item in trace if item.get("type") == "tool_call"]
    tool_results = [item for item in trace if item.get("type") == "tool_result"]
    delivered = json.dumps(provider_requests[0], ensure_ascii=False) if provider_requests else ""
    checks = {
        "five_local_provider_requests": len(provider_requests) == 5,
        "source_and_catalog_reached_provider":
            catalog["baseline"]["source_sha256"] in delivered
            and catalog["event"]["source_sha256"] in delivered
            and all(identifier in delivered for identifier in ids),
        "four_tool_calls_paired": len(tool_calls) == len(tool_results) == 4
            and {x["id"] for x in tool_calls} == {x["id"] for x in tool_results},
        "one_linked_review": len(state["theses"][0]["reviews"]) == 1
            and state["theses"][0]["reviews"][0]["alert_id"] == alert["id"],
        "blocked_and_acknowledged": state["theses"][0]["thesis"]["actionability"] == "blocked"
            and state["alerts"][0]["status"] == "acknowledged",
        "reference_candidate_only": card["status"] == "candidate_for_qualitative_review"
            and card["quality_pass"] is None,
    }
    return {"status": "free_scripted_source_distinct_gateway_replay",
            "case_id": fixture["case_id"], "checks": checks,
            "all_checks_passed": all(checks.values()),
            "model_observations": 0, "external_provider_requests": 0,
            "estimated_external_cost_usd": 0, "quality_pass": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    result = run(args.template_db, args.gateway_binary)
    if not result["all_checks_passed"]:
        raise AssertionError("source-distinct scripted Gateway checks failed")
    manifest = {"script_sha256": sha256(Path(__file__)),
                "fixture_builder_sha256": sha256(
                    HERE / "build_reference_source_distinct_event_fixtures_v1.py"),
                "plugin_sha256": sha256(PLUGIN_PATH),
                "gateway_binary_sha256": sha256(args.gateway_binary),
                "template_db_sha256": sha256(args.template_db),
                "provider": "local_scripted_loopback_no_external_api"}
    args.output_dir.mkdir(parents=True)
    for filename, data in (("RESULT.json", result), ("MANIFEST.json", manifest)):
        (args.output_dir / filename).write_text(json.dumps(data, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
