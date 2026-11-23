#!/usr/bin/env python3
"""Run the first five source-audited event cases with five fresh sessions each.

The source-audited batch is prospective, but five cases alone cannot establish
the planned 20-cluster reliability claim. No outcome-based retries are allowed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import build_prospective_event_batch1_v1 as source_batch
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


MODEL = "deepseek/deepseek-v4-flash"
# Conservative peak rates, verified against official DeepSeek pricing on 2026-10-23.
# The legacy model name currently routes to DeepSeek-V4.1-Flash-1017.
PRICING = {MODEL: {"input_per_million": 0.30, "output_per_million": 1.20,
                   "cache_read_per_million": 0.006}}
ESTIMATED_SPEND_STOP_USD = 0.25
NEXT_OBSERVATION_RESERVE_USD = 0.05


def review_prompt(case_id: str, thesis_id: str, alert_id: str) -> str:
    return (
        "This is a historical SEC research-state replay, not a trade request. "
        "Read the stored thesis and earnings alert using finance tools. Compare the "
        "selected adjacent-quarter facts with correct units and basis; for percent "
        "metrics, distinguish percentage-point from relative-percent changes. "
        "Explain a supported implication, a material counterpoint, and evidence still "
        "needed. Do not assume the selected facts exhaust the filing or establish a "
        "causal explanation. Choose your own thesis-review decision. Record a "
        "version-protected review linked to the alert and its source hash, then "
        "acknowledge the alert using its observed version. Do not trade. "
        f"Case {case_id}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


def startup_diagnostics(log_text: str) -> dict[str, bool]:
    """Record only startup markers, never raw logs with possible secrets."""
    return {"gateway_started": 'msg="gateway started"' in log_text,
            "finance_plugin_seen": "finance-tools" in log_text}


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
    pilot.turn(review_prompt(fixture["case_id"], thesis["id"], alert["id"]))
    state = pilot.ledger_state()
    alerts = state["alerts"]
    theses = state["theses"]
    reviews = theses[0]["reviews"] if len(theses) == 1 else []
    checks = {
        "one_thesis_and_alert": len(theses) == 1 and len(alerts) == 1,
        "source_packet_exact": len(alerts) == 1 and
                               alerts[0]["event"]["sources"] == event["sources"] and
                               alerts[0]["event"]["observed_metrics"] == event["observed_metrics"],
        "one_linked_review": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"] and
                             reviews[0]["event"]["sources"] == event["sources"],
        "alert_acknowledged": len(alerts) == 1 and alerts[0]["status"] == "acknowledged",
        "state_actionability_consistent": len(reviews) == 1 and
             (theses[0]["thesis"]["actionability"] == "blocked"
              if reviews[0]["decision"] == "needs_review"
              else theses[0]["thesis"]["actionability"] == "available"),
    }
    return state, checks


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--preflight-only", action="store_true")
    cli.add_argument("--template-db", type=Path)
    cli.add_argument("--gateway-binary", type=Path)
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument("--authorize-paid-run", action="store_true",
                     help="Required acknowledgment before any model call")
    args = cli.parse_args()
    prepared = source_batch.preflight()
    if args.preflight_only:
        print(json.dumps({key: value for key, value in prepared.items() if key != "fixtures"},
                         ensure_ascii=False, indent=2))
        return
    if not args.authorize_paid_run:
        cli.error("--authorize-paid-run is required for paid execution")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        cli.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway template DB or binary missing")
    base.MODEL, base.PRICING, base.CAP_USD = MODEL, PRICING, ESTIMATED_SPEND_STOP_USD
    panel.MODEL = MODEL
    order = [(fixture, repeat) for repeat in range(1, 6)
             for fixture in prepared["fixtures"]]
    paths = [Path(__file__).resolve(), source_batch.FRAME_PATH,
             Path(source_batch.__file__).resolve(),
             source_batch.MANIFEST_PATH, source_batch.LOCK_PATH,
             HERE / "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
             HERE / "PROSPECTIVE-CROSS-WORKFLOW-HOLDOUT-v1.md",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "workflow_runtime_audit_v2.py",
             HERE / "run_thesis_event_gateway.py",
             HERE / "run_thesis_event_panel.py", PLUGIN_PATH,
             *(HERE / case["packet"] for case in
               json.loads(source_batch.FRAME_PATH.read_text())["cases"])]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model_requested=MODEL, model_version_expected="DeepSeek-V4.1-Flash-1017",
                    pricing_peak_usd_per_million=PRICING[MODEL],
                    pricing_checked_at="2026-10-23",
                    estimated_spend_stop_usd=ESTIMATED_SPEND_STOP_USD,
                    next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
                    run_order=[f"{fixture['case_id']}-r{repeat}"
                               for fixture, repeat in order],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_packet_sha256=prepared["source_packet_sha256"],
                    source_boundary="selected SEC Exhibit 99.1 facts; no live source fetch")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="prospective-event-batch1-") as temp_root:
        for fixture, repeat in order:
            if spent + NEXT_OBSERVATION_RESERVE_USD > ESTIMATED_SPEND_STOP_USD:
                print("STOP: insufficient estimated reserve for next observation", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repeat}"
            pilot, process, log = None, None, None
            startup = {"gateway_started": False, "finance_plugin_seen": False}
            state, checks, error = None, {}, None
            try:
                pilot = panel.PanelPilot(observation_id, args.template_db,
                                         args.gateway_binary, temp_root, False, spent)
                process, log = base.start_gateway(pilot.home)
                startup = startup_diagnostics(
                    (pilot.home / "gateway.log").read_text(errors="replace"))
                if not all(startup.values()):
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
            cost = pilot.cost if pilot is not None else 0.0
            runtime = audit_turns(turns)
            spent += cost
            result = {
                "observation_id": observation_id, "case_id": fixture["case_id"],
                "repetition": repeat, "workflow": "sec_event_to_thesis_review",
                "status": "mechanical_pass" if error is None and checks and
                          all(checks.values()) and runtime["clean_completion"] else "needs_review",
                "quality_score": None, "error": error, "checks": checks,
                "startup": startup, "runtime_audit": runtime, "state": state,
                "turns": turns, "estimated_cost_usd": cost,
            }
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id, "status": result["status"],
                              "error": error, "cumulative_estimated_cost_usd": spent}),
                  flush=True)
            if (error or runtime["request_errors"] or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"]):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
