#!/usr/bin/env python3
"""Preflight or run a new 20-case/100-session source-distinct SEC event arm.

The previous v2/v3 observations are not resumed, retried or pooled. Paid calls
require a separate user authorization flag, spend cap and unused result path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_postcorrection_event_holdout_v2 as old_runner
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


MODEL = old_runner.MODEL
PRICING = old_runner.PRICING
EXPECTED_PROVIDER_VERSION = old_runner.EXPECTED_PROVIDER_VERSION
PRICING_CHECKED_AT = "2026-10-25"
PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing/"
MAX_TOKENS = 8192
MAX_TOOL_ITERATIONS = 16
NEXT_OBSERVATION_RESERVE_USD = 0.10
ORDER_SEED = "postcorrection-v4-source-distinct-event-precommitted"


def planned_order(fixtures: list[dict]) -> list[tuple[dict, int]]:
    entries = [(item, repetition) for item in fixtures for repetition in range(1, 6)]
    return sorted(entries, key=lambda pair: hashlib.sha256(
        f"{ORDER_SEED}:{pair[0]['case_id']}:r{pair[1]}".encode()).hexdigest())


class V4Pilot(panel.PanelPilot):
    def __init__(self, case_id, template_db, binary, temp_root, synthetic, spent_so_far):
        super().__init__(case_id, template_db, binary, temp_root, synthetic, spent_so_far)
        # Only the isolated copied DB is touched. The user's running service is not.
        with sqlite3.connect(self.home / "fastclaw.db") as database:
            row = database.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
            if row is None:
                raise ValueError("copied Gateway DB lacks finance coordinator")
            config = json.loads(row[0])
            config.update(maxTokens=MAX_TOKENS, maxToolIterations=MAX_TOOL_ITERATIONS)
            database.execute("UPDATE agents SET config=? WHERE id=?",
                             (json.dumps(config), AGENT_ID))
            actual = json.loads(database.execute(
                "SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()[0])
            if (actual.get("maxTokens") != MAX_TOKENS
                    or actual.get("maxToolIterations") != MAX_TOOL_ITERATIONS
                    or actual.get("model") != MODEL):
                raise AssertionError("isolated coordinator configuration differs")


def run_case(pilot, fixture: dict) -> tuple[dict, dict]:
    seed, event = fixture["seed_thesis"], fixture["event"]
    thesis = must_call(pilot.finance, "thesis_save", seed, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": fixture["runtime_symbol"],
        "thesis_id": thesis["id"], "event_types": ["earnings"],
        "keywords": [source_batch.watchlist_keyword(fixture["runtime_symbol"])],
        "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": fixture["runtime_symbol"], "event": event,
    }, pilot.tenant)["results"][0]["alert"]
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
    paths = {Path(__file__), Path(source_batch.__file__),
             Path(old_runner.__file__),
             HERE / "POSTCORRECTION-V4-INSIGHT-QUALITY-PROTOCOL.md",
             HERE / "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
             HERE / "prepare_postcorrection_v4_judgment.py",
             HERE / "prepare_postcorrection_judgment_v2.py",
             HERE / "aggregate_postcorrection_judgments_v2.py",
             HERE / "audit_postcorrection_v4_source_identity.py",
             HERE / "audit_v4_declared_sec_rows.py",
             HERE / "audit_wex_v4_source_facts.py",
             HERE / "audit_hban_v4_source_facts.py",
             HERE / "audit_vrsk_v4_source_facts.py",
             HERE / "audit_ntrs_v4_source_facts.py",
             HERE / "postcorrection_unseen_source_candidates_v4.json",
             HERE / "postcorrection_v4_remaining16_provisional_pairs.json",
             HERE / "workflow_runtime_audit_v2.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_thesis_event_gateway.py",
             HERE / "run_thesis_event_panel.py",
             PLUGIN_PATH, PLUGIN_PATH.with_name("accounting_lineage.py"),
             PLUGIN_PATH.with_name("plugin.json")}
    paths.update(source_batch.FIRST_PACKETS.values())
    paths.update(source_batch.DECLARED_PACKETS.values())
    for directory in source_batch.MANIFEST_DIRS:
        paths.update(path for path in directory.iterdir() if path.is_file())
    return sorted(paths)


def write_hash_list(output_dir: Path) -> None:
    paths = [output_dir / "manifest.json", *output_dir.glob("*/result.json"),
             *output_dir.glob("*/finance-tools.db")]
    (output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output_dir)}\n" for path in sorted(paths)))


def preflight() -> dict:
    prepared = source_batch.preflight()
    order = planned_order(prepared["fixtures"])
    run_ids = [f"{item['case_id']}-r{repeat}" for item, repeat in order]
    if (len(order) != 100 or len(set(run_ids)) != 100
            or prepared["rendered_signed_bridges"] != 94):
        raise AssertionError("v4 source/bridge/order preflight differs")
    return {"prepared": prepared, "order": order, "run_ids": run_ids,
            "order_hash": hashlib.sha256(json.dumps(run_ids).encode()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-run", action="store_true",
                        help="Only after separate user authorization for v4")
    args = parser.parse_args()
    frozen = preflight()
    if args.preflight_only:
        print(json.dumps({"status": "v4_ready_for_separate_authorization_not_executed",
                          "cases": 20, "planned_observations": 100,
                          "rendered_signed_bridges": 94, "model_observations": 0,
                          "model_requested": MODEL,
                          "max_tokens": MAX_TOKENS,
                          "max_tool_iterations": MAX_TOOL_ITERATIONS,
                          "run_order_sha256": frozen["order_hash"]}, indent=2))
        return
    if not args.authorize_paid_run:
        parser.error("--authorize-paid-run is required for external model calls")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.estimated_spend_cap_usd is None or not (
            NEXT_OBSERVATION_RESERVE_USD < args.estimated_spend_cap_usd <= 10):
        parser.error("a positive bounded estimated spend cap is required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway template DB or binary missing")
    base.MODEL, base.PRICING, base.CAP_USD = MODEL, PRICING, args.estimated_spend_cap_usd
    panel.MODEL = MODEL
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in manifest_paths()}
    manifest.update(model_requested=MODEL,
                    model_version_expected=EXPECTED_PROVIDER_VERSION,
                    pricing_estimate=PRICING[MODEL],
                    pricing_source=PRICING_SOURCE,
                    pricing_checked_at=PRICING_CHECKED_AT,
                    estimated_spend_stop_usd=args.estimated_spend_cap_usd,
                    next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
                    coordinator_max_tokens=MAX_TOKENS,
                    coordinator_max_tool_iterations=MAX_TOOL_ITERATIONS,
                    run_order=frozen["run_ids"],
                    run_order_sha256=frozen["order_hash"],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_boundary="frozen selected SEC rows; no live source fetch",
                    quality_score_stage="blinded post-run claim-level adjudication")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="postcorrection-event-v4-") as temp_root:
        for fixture, repetition in frozen["order"]:
            if spent + NEXT_OBSERVATION_RESERVE_USD > args.estimated_spend_cap_usd:
                print("STOP: insufficient estimated reserve for next observation", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repetition}"
            pilot, process, log = None, None, None
            state, checks, error = None, {}, None
            try:
                pilot = V4Pilot(observation_id, args.template_db,
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
                shutil.copy2(pilot.home / "finance-tools.db",
                             directory / "finance-tools.db")
            write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"] or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"] or spent > args.estimated_spend_cap_usd):
                print("STOP: request error, uncertain pricing, or spend cap", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(frozen["order"]),
                      "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
