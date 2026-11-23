#!/usr/bin/env python3
"""Free scripted Gateway seam replay for reference-only SEC conclusions."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import build_reference_insight_prompt_v1 as prompt_contract
import run_finance_gateway_fault_replay as local
import run_finance_workflow_pilot as base
import run_insight_candidate_gateway_replay_v1 as previous
import run_postcorrection_gateway_replay_v2 as gateway
from reference_insight_catalog_v1 import build_catalog
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_insight_candidate_v1 import canonical_state
from verify_reference_insight_candidate_v1 import render_reference_card


def run_case(template_db: Path, binary: Path, fixture: dict, catalog: dict,
             temp_root: str, bad_reference: bool) -> dict:
    branch = "unknown_ref" if bad_reference else "known_refs"
    symbol = fixture["runtime_symbol"]
    pilot = base.Pilot("reference-insight-" + branch, template_db, binary,
                       temp_root, False, 0.0)
    thesis = must_call(pilot.finance, "thesis_save", fixture["seed_thesis"],
                       pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [symbol], "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": fixture["event"],
    }, pilot.tenant)["results"][0]["alert"]
    evidence = [fixture["seed_thesis"]["evidence"][0],
                fixture["event"]["sources"][0]]
    calls = [
        local.tool_stream("read-thesis", "finance-tools__thesis_get",
                          {"thesis_id": thesis["id"]}),
        local.tool_stream("read-alert", "finance-tools__alert_list", {}),
        local.tool_stream("save-review", "finance-tools__thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": thesis["version"],
            "event": {"summary": alert["event"]["summary"]},
            "impact": "mixed", "decision": "needs_review",
            "rationale": "Selected earnings signals are mixed and need source-linked follow-up.",
            "evidence": evidence, "next_review_at": "2026-11-30", "causal_claims": [],
        }),
        local.tool_stream("ack-alert", "finance-tools__alert_update", {
            "alert_id": alert["id"], "status": "acknowledged",
            "expected_version": alert["version"],
        }),
    ]

    def final_candidate() -> dict:
        return {
            "selected_comparisons": {
                "support": ["SEQ:invented" if bad_reference
                            else "SEQ:gaap_net_interest_income"],
                "counterevidence": ["SEQ:gaap_credit_loss_provision"],
            },
            "interpretation": {
                "implication": "Reported improvement is limited by its composition.",
                "counterevidence": "Higher credit costs offset much of the improvement.",
                "uncertainty": "Revenue mix and credit-cost drivers require further research.",
            },
            "asserted_state": canonical_state(pilot.ledger_state()),
        }

    with previous.DynamicCandidateProvider(calls, final_candidate) as provider:
        local.configure_provider(pilot.home, provider.url)
        process, log = base.start_gateway(pilot.home)
        try:
            response = gateway.gateway_turn(
                pilot, prompt_contract.reference_prompt(
                    fixture, catalog, thesis["id"], alert["id"]),
                symbol + "-reference-" + branch)
        finally:
            base.stop_gateway(process, log)
        requests = provider.requests
    state = pilot.ledger_state()
    final = response["choices"][0]["message"].get("content")
    candidate = json.loads(final)
    card = render_reference_card(catalog, candidate, state)
    trace = response.get("fastclaw", {}).get("trace", [])
    tool_calls = [item for item in trace if item.get("type") == "tool_call"]
    tool_results = [item for item in trace if item.get("type") == "tool_result"]
    provider_prompt = json.dumps(requests[0], ensure_ascii=False) if requests else ""
    checks = {
        "local_provider_five_requests": len(requests) == 5,
        "reference_catalog_and_schema_prompt_delivered":
            "SEQ:gaap_net_interest_income" in provider_prompt
            and "selected_comparisons" in provider_prompt
            and catalog["event"]["source_sha256"] in provider_prompt,
        "four_tool_calls_paired": len(tool_calls) == len(tool_results) == 4
            and {item["id"] for item in tool_calls}
            == {item["id"] for item in tool_results},
        "one_review_and_blocked_state": len(state["theses"][0]["reviews"]) == 1
            and state["theses"][0]["thesis"]["actionability"] == "blocked"
            and state["alerts"][0]["status"] == "acknowledged",
        "gate_expected_branch": card["status"] == (
            "held" if bad_reference else "candidate_for_qualitative_review"),
        "no_quality_pass_inferred": card["quality_pass"] is None,
    }
    if bad_reference:
        checks["invented_ref_visible"] = card["issues"] == [
            "support_comparison_refs_invalid"]
    else:
        checks["full_host_table_retained"] = (
            set(card["complete_host_comparison_table"]) == set(catalog["rows"])
            and card["complete_host_comparison_table"][
                "SEQ:gaap_net_interest_income"]["delta_value"] == "25")
    return {"branch": branch, "checks": checks,
            "all_checks_passed": all(checks.values()),
            "card": card, "model_observations": 0,
            "external_provider_requests": 0,
            "estimated_external_cost_usd": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    fixture = next(item for item in source_batch.preflight()["fixtures"]
                   if item["runtime_symbol"] == "FITB")
    packet_path = source_batch.DECLARED_PACKETS["FITB"]
    catalog = build_catalog("FITB", json.loads(packet_path.read_text()))
    with tempfile.TemporaryDirectory(prefix="reference-insight-gateway-") as temp_root:
        results = [run_case(args.template_db, args.gateway_binary, fixture,
                            catalog, temp_root, bad)
                   for bad in (False, True)]
    summary = {"status": "free_scripted_reference_insight_gateway_replay",
               "branches": len(results),
               "all_checks_passed": all(item["all_checks_passed"] for item in results),
               "model_observations": 0, "external_provider_requests": 0,
               "estimated_external_cost_usd": 0, "quality_pass": None}
    paths = [Path(__file__), Path(source_batch.__file__), Path(previous.__file__),
             Path(prompt_contract.__file__), Path(local.__file__), Path(gateway.__file__),
             Path(PLUGIN_PATH), HERE / "reference_insight_catalog_v1.py",
             HERE / "verify_reference_insight_candidate_v1.py", packet_path]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api")
    args.output_dir.mkdir(parents=True)
    for name, data in (("known_refs.json", results[0]),
                       ("unknown_ref.json", results[1]),
                       ("SUMMARY.json", summary), ("manifest.json", manifest)):
        (args.output_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in sorted(
            args.output_dir.glob("*.json"))))
    print(json.dumps(summary, indent=2))
    if not summary["all_checks_passed"]:
        raise AssertionError("scripted reference-insight Gateway replay failed")


if __name__ == "__main__":
    main()
