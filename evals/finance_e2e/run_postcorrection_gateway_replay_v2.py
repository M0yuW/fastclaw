#!/usr/bin/env python3
"""Free, local scripted-provider Gateway seam replay for audited SEC cases.

This verifies prompt delivery, actual finance tool calls, source-bound state,
and needs_review actionability. It does not judge model reasoning and never
contacts DeepSeek or counts as a v2 model observation.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import urllib.request
from pathlib import Path

import build_postcorrection_event_preflight_v2 as source_batch
import run_finance_gateway_fault_replay as local
import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, sha256


def gateway_turn(pilot, prompt: str, symbol: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:18955/v1/chat/completions",
        data=json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "fastclaw": {"eval": True, "include_trace": True,
                         "include_usage_breakdown": True,
                         "server_timeout_ms": 120000},
        }).encode(),
        headers={"Authorization": "Bearer " + pilot.token,
                 "Content-Type": "application/json",
                 "x-fastclaw-agent-id": AGENT_ID,
                 "x-fastclaw-session-key": "postcorrection-v2-scripted-" + symbol.lower()},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=130) as handle:
        return json.load(handle)


def run(template_db: Path, binary: Path, symbol: str = "AXP",
        fixtures: list[dict] | None = None) -> dict:
    fixtures = fixtures if fixtures is not None else source_batch.preflight()["fixtures"]
    fixture = next(item for item in fixtures if item["runtime_symbol"] == symbol)
    with tempfile.TemporaryDirectory(prefix="v2-scripted-gateway-") as root:
        pilot = base.Pilot("v2-scripted-" + symbol.lower(),
                           template_db, binary, root, False, 0.0)
        thesis = must_call(pilot.finance, "thesis_save", fixture["seed_thesis"], pilot.tenant)["thesis"]
        must_call(pilot.finance, "watchlist_save", {
            "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
            "event_types": ["earnings"], "keywords": [symbol], "min_match_score": 1,
        }, pilot.tenant)
        alert = must_call(pilot.finance, "event_alert_ingest", {
            "market": "US", "symbol": symbol, "event": fixture["event"],
        }, pilot.tenant)["results"][0]["alert"]
        prompt = source_batch.review_prompt(fixture, thesis["id"], alert["id"])
        responses = [
            local.tool_stream("read-thesis", "finance-tools__thesis_get",
                              {"thesis_id": thesis["id"]}),
            local.tool_stream("read-alert", "finance-tools__alert_list", {}),
            local.tool_stream("write-review", "finance-tools__thesis_record_review", {
                "thesis_id": thesis["id"], "alert_id": alert["id"],
                "expected_version": thesis["version"],
                "event": {"summary": alert["event"]["summary"]},
                "impact": "mixed", "decision": "needs_review",
                "rationale": "Scripted local fixture defers the research-state decision.",
            }),
            local.tool_stream("ack-alert", "finance-tools__alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"],
            }),
            local.text_stream(f"Local scripted {symbol} research state is on hold."),
        ]
        with local.ScriptedProvider(responses) as provider:
            local.configure_provider(pilot.home, provider.url)
            process, log = base.start_gateway(pilot.home)
            try:
                response = gateway_turn(pilot, prompt, symbol)
            finally:
                base.stop_gateway(process, log)
            provider_requests = provider.requests
            received = provider.received
            unused = len(provider.responses)
        state = pilot.ledger_state()
    trace = response.get("fastclaw", {}).get("trace", [])
    calls = [item for item in trace if item.get("type") == "tool_call"]
    results = [item for item in trace if item.get("type") == "tool_result"]
    rendered_requests = json.dumps(provider_requests, ensure_ascii=False)
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    held = state["theses"][0]["thesis"]
    reviews = state["theses"][0]["reviews"]
    event_fact_id = next(iter(fixture["event"]["observed_metrics"].values()))["fact_id"]
    checks = {
        "provider_local_only": received == 5 and unused == 0,
        "host_numeric_context_reached_provider":
            "Displayed-value comparisons" in rendered_requests
            and event_fact_id in rendered_requests
            and fixture["case_id"] in rendered_requests
            and fixture["event"]["sources"][0]["sha256"] in rendered_requests,
        "actual_tools_called_and_results_paired": len(calls) == len(results) == 4
            and {item["id"] for item in calls} == {item["id"] for item in results},
        "source_bound_review_persisted": len(reviews) == 1
            and reviews[0]["alert_id"] == alert["id"]
            and reviews[0]["event"]["sources"] == fixture["event"]["sources"],
        "voluntary_hold_blocks_actionability": held["decision_hold"]
            and held["actionability"] == "blocked"
            and held["decision_hold_alert_id"] == alert["id"]
            and held["conviction"] == 3,
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "terminal_text_matches_script": final == f"Local scripted {symbol} research state is on hold.",
    }
    return {"status": "local_scripted_gateway_replay_only",
            "case_id": fixture["case_id"], "checks": checks,
            "provider_requests": received, "tool_calls": len(calls),
            "tool_results": len(results), "model_observations": 0,
            "external_provider_requests": 0, "estimated_external_cost_usd": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--symbol", choices=sorted(source_batch.READY), default="AXP")
    selection.add_argument("--all-ready", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway template DB or binary missing")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), Path(source_batch.__file__),
             Path(local.__file__), Path(base.__file__),
             HERE / "run_thesis_event_panel.py",
             HERE / "selected_fact_delta_guard_v1.py",
             HERE / "rank_postcorrection_holdout_v2.py",
             HERE / "postcorrection_holdout_frame_v2.json",
             HERE / "prospective_pair_sources_manifest_v1.json",
             HERE / "prospective_pair_sources_lock_v1.json",
             HERE / "postcorrection_pair_sources_manifest_v2.json",
             HERE / "postcorrection_pair_sources_lock_v2.json",
             HERE / "results/2026-10-23-prospective-event-batch1-flash-v1/RESULT-SHA256.txt",
             PLUGIN_PATH]
    paths.extend(path for auditor, path in source_batch.READY.values())
    paths.extend(Path(auditor.__file__) for auditor, _ in source_batch.READY.values())
    for lock_name in ("prospective_pair_sources_lock_v1.json",
                      "postcorrection_pair_sources_lock_v2.json"):
        locked = json.loads((HERE / lock_name).read_text())
        paths.extend(HERE / entry["local_path"] for entry in locked["entries"])
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_no_external_api",
                    selected_symbols=(sorted(source_batch.READY) if args.all_ready
                                      else [args.symbol]))
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    fixtures = source_batch.preflight()["fixtures"]
    symbols = sorted(source_batch.READY) if args.all_ready else [args.symbol]
    results = []
    for symbol in symbols:
        result = run(args.template_db, args.gateway_binary, symbol, fixtures)
        results.append(result)
        name = f"result-{symbol}.json" if args.all_ready else "result.json"
        (args.output_dir / name).write_text(json.dumps(result, indent=2) + "\n")
        hash_paths = [args.output_dir / "manifest.json",
                      *sorted(args.output_dir.glob("result*.json"))]
        (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
            f"{sha256(path)}  {path.name}\n" for path in hash_paths))
        print(json.dumps({"symbol": symbol, "checks_passed": all(result["checks"].values()),
                          "completed": len(results), "planned": len(symbols),
                          "external_provider_requests": 0}, ensure_ascii=False), flush=True)
    summary = {"status": "local_scripted_gateway_replay_only",
               "cases": len(results), "all_checks_passed": all(
                   all(item["checks"].values()) for item in results),
               "model_observations": 0, "external_provider_requests": 0,
               "estimated_external_cost_usd": 0}
    (args.output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    hash_paths = [args.output_dir / "manifest.json", args.output_dir / "SUMMARY.json",
                  *sorted(args.output_dir.glob("result*.json"))]
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in hash_paths))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary["all_checks_passed"]:
        raise AssertionError("local scripted Gateway seam replay failed")


if __name__ == "__main__":
    main()
