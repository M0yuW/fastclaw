#!/usr/bin/env python3
"""Prepare or run the 20-case, five-session SEC event holdout.

Preflight is local and free. Paid execution requires a separate, explicit user
authorization, an operator-supplied estimated spend cap, and a fresh output
directory. No outcome-based retry or overwrite path is provided.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import build_postcorrection_event_preflight_v2 as source_batch
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


MODEL = "deepseek/deepseek-v4-flash"
# Conservative peak-hour rates from the official provider pricing page. The
# legacy model alias routes to V4.1-Flash-1017 as of the checked date.
PRICING = {MODEL: {"input_per_million": 0.30, "output_per_million": 1.20,
                   "cache_read_per_million": 0.006}}
PRICING_CHECKED_AT = "2026-10-24"
PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
ROUTING_SOURCE = "https://api-docs.deepseek.com/updates/"
EXPECTED_PROVIDER_VERSION = "DeepSeek-V4.1-Flash-1017"
NEXT_OBSERVATION_RESERVE_USD = 0.05
ORDER_SEED = "postcorrection-sec-event-v2-precommitted-order"


def planned_order(fixtures: list[dict]) -> list[tuple[dict, int]]:
    entries = [(item, repetition) for item in fixtures for repetition in range(1, 6)]
    return sorted(entries, key=lambda pair: hashlib.sha256(
        f"{ORDER_SEED}:{pair[0]['case_id']}:r{pair[1]}".encode()).hexdigest())


def run_case(pilot, fixture: dict) -> tuple[dict, dict]:
    seed, event = fixture["seed_thesis"], fixture["event"]
    thesis = must_call(pilot.finance, "thesis_save", seed, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": fixture["runtime_symbol"],
        "thesis_id": thesis["id"], "event_types": ["earnings"],
        "keywords": [fixture["runtime_symbol"]], "min_match_score": 1,
    }, pilot.tenant)
    ingest = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": fixture["runtime_symbol"], "event": event,
    }, pilot.tenant)
    alert = ingest["results"][0]["alert"]
    pilot.turn(source_batch.review_prompt(fixture, thesis["id"], alert["id"]))
    state = pilot.ledger_state()
    alerts, theses = state["alerts"], state["theses"]
    reviews = theses[0]["reviews"] if len(theses) == 1 else []
    checks = {
        "one_thesis_and_alert": len(theses) == len(alerts) == 1,
        "source_packet_exact": len(alerts) == 1
            and alerts[0]["event"]["sources"] == event["sources"]
            and alerts[0]["event"]["observed_metrics"] == event["observed_metrics"],
        "one_linked_review": len(reviews) == 1
            and reviews[0]["alert_id"] == alert["id"]
            and reviews[0]["event"]["sources"] == event["sources"],
        "alert_acknowledged": len(alerts) == 1
            and alerts[0]["status"] == "acknowledged",
        "state_actionability_consistent": len(reviews) == 1 and (
            theses[0]["thesis"]["actionability"] == "blocked"
            if reviews[0]["decision"] == "needs_review"
            else theses[0]["thesis"]["actionability"] == "available"),
    }
    return state, checks


def manifest_paths() -> list[Path]:
    paths = [Path(__file__), Path(source_batch.__file__),
             HERE / "POSTCORRECTION-HOLDOUT-PROTOCOL-v2.md",
             HERE / "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
             HERE / "POSTCORRECTION-JUDGMENT-WORKFLOW-v2.md",
             HERE / "prepare_postcorrection_judgment_v2.py",
             HERE / "aggregate_postcorrection_judgments_v2.py",
             HERE / "postcorrection_holdout_frame_v2.json",
             HERE / "rank_postcorrection_holdout_v2.py",
             HERE / "selected_fact_delta_guard_v1.py",
             HERE / "financial_evidence_bundle_v1.py",
             HERE / "fetch_sources.py",
             HERE / "workflow_runtime_audit_v2.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_thesis_event_gateway.py",
             HERE / "run_thesis_event_panel.py",
             HERE / "prospective_pair_sources_manifest_v1.json",
             HERE / "prospective_pair_sources_lock_v1.json",
             HERE / "postcorrection_pair_sources_manifest_v2.json",
             HERE / "postcorrection_pair_sources_lock_v2.json",
             HERE / "results/2026-10-23-prospective-event-batch1-flash-v1/RESULT-SHA256.txt",
             PLUGIN_PATH, PLUGIN_PATH.with_name("accounting_lineage.py"),
             PLUGIN_PATH.with_name("plugin.json")]
    paths.extend(path for auditor, path in source_batch.READY.values())
    paths.extend(Path(auditor.__file__) for auditor, _ in source_batch.READY.values())
    for lock_name in ("prospective_pair_sources_lock_v1.json",
                      "postcorrection_pair_sources_lock_v2.json"):
        lock = json.loads((HERE / lock_name).read_text())
        paths.extend(HERE / entry["local_path"] for entry in lock["entries"])
    return sorted(set(paths))


def write_hash_list(output_dir: Path) -> None:
    paths = [output_dir / "manifest.json", *output_dir.glob("*/result.json"),
             *output_dir.glob("*/finance-tools.db")]
    (output_dir / "RESULT-SHA256.txt").write_text(
        "".join(f"{sha256(path)}  {path.relative_to(output_dir)}\n"
                for path in sorted(paths)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-run", action="store_true",
                        help="Use only after separate user authorization for this v2 batch")
    args = parser.parse_args()
    prepared = source_batch.preflight()
    if prepared["ready_cases"] != 20 or prepared["target_cases"] != 20:
        raise AssertionError("20 source-audited cases required")
    order = planned_order(prepared["fixtures"])
    if len(order) != 100 or len({(item["case_id"], rep) for item, rep in order}) != 100:
        raise AssertionError("expected 100 unique case-repetition pairs")
    run_ids = [f"{item['case_id']}-r{rep}" for item, rep in order]
    if args.preflight_only:
        print(json.dumps({"status": "ready_for_separate_authorization_not_executed",
                          "source_ready_cases": prepared["ready_cases"],
                          "planned_observations": len(order), "model_observations": 0,
                          "run_order_sha256": hashlib.sha256(
                              json.dumps(run_ids).encode()).hexdigest(),
                          "historical_v1_cost_usd_for_25": 0.187249212,
                          "historical_v1_100_observation_extrapolation_usd": 0.748996848,
                          "provider_peak_price_check_date": PRICING_CHECKED_AT,
                          "expected_provider_version": EXPECTED_PROVIDER_VERSION}, indent=2))
        return
    if not args.authorize_paid_run:
        parser.error("--authorize-paid-run is required for model calls")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.estimated_spend_cap_usd is None or not (
            NEXT_OBSERVATION_RESERVE_USD < args.estimated_spend_cap_usd <= 10):
        parser.error("a positive, bounded --estimated-spend-cap-usd is required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway template DB or binary missing")
    base.MODEL, base.PRICING = MODEL, PRICING
    base.CAP_USD = args.estimated_spend_cap_usd
    panel.MODEL = MODEL
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in manifest_paths()}
    manifest.update(model_requested=MODEL,
                    model_version_expected=EXPECTED_PROVIDER_VERSION,
                    pricing_estimate=PRICING[MODEL],
                    pricing_checked_at=PRICING_CHECKED_AT,
                    pricing_source=PRICING_SOURCE,
                    routing_source=ROUTING_SOURCE,
                    estimated_spend_stop_usd=args.estimated_spend_cap_usd,
                    next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
                    run_order=run_ids,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_boundary="selected audited SEC facts; no live source fetch",
                    quality_score_stage="post-run claim-level adjudication")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="postcorrection-event-v2-") as temp_root:
        for fixture, repetition in order:
            if spent + NEXT_OBSERVATION_RESERVE_USD > args.estimated_spend_cap_usd:
                print("STOP: insufficient estimated reserve for next observation", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repetition}"
            pilot, process, log = None, None, None
            state, checks, error = None, {}, None
            try:
                pilot = panel.PanelPilot(observation_id, args.template_db,
                                         args.gateway_binary, temp_root, False, spent)
                process, log = base.start_gateway(pilot.home)
                startup_log = (pilot.home / "gateway.log").read_text(errors="replace")
                if 'msg="gateway started"' not in startup_log or "finance-tools" not in startup_log:
                    raise RuntimeError("finance plugin startup not confirmed")
                state, checks = run_case(pilot, fixture)
                trace_checks, _ = panel.trace_checks(pilot)
                checks.update(trace_checks)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if pilot is not None:
                    try:
                        state = pilot.ledger_state()
                    except Exception:
                        pass
            finally:
                if process is not None and log is not None:
                    base.stop_gateway(process, log)
            turns = pilot.turns if pilot is not None else []
            runtime = audit_turns(turns)
            cost = pilot.cost if pilot is not None else 0.0
            spent += cost
            result = {"observation_id": observation_id,
                      "case_id": fixture["case_id"], "repetition": repetition,
                      "workflow": "sec_event_to_thesis_review",
                      "status": "mechanical_pass" if error is None and checks
                          and all(checks.values()) and runtime["clean_completion"]
                          else "needs_review",
                      "quality_score": None, "error": error, "checks": checks,
                      "runtime_audit": runtime, "state": state, "turns": turns,
                      "estimated_cost_usd": cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"] or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"] or spent > args.estimated_spend_cap_usd):
                print("STOP: request error, uncertain pricing, or spend cap", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
