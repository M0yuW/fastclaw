#!/usr/bin/env python3
"""Three fresh historical FinTech SEC screens, five isolated Flash repeats each."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
import run_sec_disclosure_screen_flash_v2 as prior
from run_thesis_event_gateway import load_plugin, must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CASE = HERE / "fintech_sec_screen_holdout_v1.json"
PROTOCOL = HERE / "FINTECH-SEC-SCREEN-HOLDOUT-PROTOCOL-v1.md"
FIXTURES = HERE / "workflow_fixtures_fintech_sec_screen_holdout_v1"
SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
CAP_USD = 0.08
REPETITIONS = 5
CASE_ORDER = ("COIN", "HOOD", "SQ")
RUN_ORDER = [(symbol, repeat) for repeat in range(1, REPETITIONS + 1)
             for symbol in CASE_ORDER]


def preflight():
    case = json.loads(CASE.read_text())
    if case["panel_id"] != "FINTECH-SEC-SCREEN-HOLDOUT-v1" or not SCRIPT.is_file():
        raise ValueError("frozen panel or adapter absent")
    candidates = {item["symbol"]: item for item in case["candidates"]}
    if set(candidates) != set(CASE_ORDER):
        raise ValueError("candidate set differs from frozen panel")
    for symbol, candidate in candidates.items():
        if sha256(HERE / candidate["local_path"]) != candidate["source_sha256"]:
            raise ValueError(f"SEC source hash mismatch for {symbol}")
    coin = candidates["COIN"]["reported"]
    derived = (coin["total_revenue_q3_2024_usd_thousand"] /
               coin["total_revenue_q3_2023_usd_thousand"] - 1) * 100
    if round(derived, 1) != coin["top_line_revenue_yoy_percent_derived"]:
        raise ValueError("COIN YoY calculation mismatch")
    with tempfile.TemporaryDirectory(prefix="fintech-sec-screen-preflight-") as folder:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(folder) / "finance.db"),
                           "finskillsPath": str(FIXTURES), "evaluationFixture": True})
        tenant = {"userId": "fintech-sec-preflight", "agentId": "finance-coordinator",
                  "sessionId": "preflight"}
        for symbol in CASE_ORDER:
            data = must_call(plugin, "screen_stocks", {
                "market": "US", "symbols": [symbol], "require_complete": False}, tenant)
            retained = candidates[symbol]["oracle_retain"]
            if ([item["symbol"] for item in data["results"]] !=
                    ([symbol] if retained else []) or
                    [item["symbol"] for item in data["rejected"]] !=
                    ([] if retained else [symbol]) or
                    data.get("synthetic") is not False or
                    data.get("offline_frozen_adapter") is not True):
                raise ValueError(f"deterministic screen mismatch for {symbol}")
    return case


def prompt(candidate):
    return (
        "Run a historical, SEC-disclosure-only candidate-research workflow for US "
        + candidate["symbol"] + ". Call finance-tools__screen_stocks with "
        "require_complete=false. This frozen offline source adapter screens only "
        "issuer-reported top-line revenue YoY growth >=20%; it is not a live quote "
        "or a seven-factor completeness screen. Read the retained or rejected item, "
        "its reported fields, exact failed criteria, source URL and full SHA-256, "
        "release date, reporting period, units and metric basis. Independently "
        "identify the most material counterpoint from a DIFFERENT supplied field; "
        "do not merely restate the screen outcome. If retained, save exactly one "
        "HISTORICAL PRELIMINARY candidate thesis with full source URL/hash in "
        "structured evidence, key numbers, the counterpoint, a discriminating "
        "follow-up question, and an explicit missing price/valuation boundary. "
        "If rejected, save no thesis, explain the exact failed criterion and why "
        "an alternate metric cannot replace it under this rule, but note any "
        "separately useful research signal. Do not trade, use live market tools, "
        "rank these issuers on a common date, or claim that passing this one rule "
        "means an attractive investment. Do not claim packet omissions are SEC "
        "filing omissions. Omit next_review_at unless genuinely future-dated."
    )


def score(candidate, pilot, state):
    symbol = candidate["symbol"]
    retained = candidate["oracle_retain"]
    theses = [item["thesis"] for item in state["theses"]]
    record = theses[0] if len(theses) == 1 else {}
    record_text = json.dumps(record, ensure_ascii=False).lower()
    evidence_text = json.dumps(record.get("evidence") or [], ensure_ascii=False).lower()
    final = workflow.final_text(pilot).lower()
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    payload = prior.tool_screen_data(pilot)
    data = payload.get("data") if isinstance(payload, dict) and payload.get("ok") else {}
    checks = {
        "screen_called": "finance-tools__screen_stocks" in calls,
        "source_locked_tool_result": bool(data) and data.get("synthetic") is False
            and data.get("offline_frozen_adapter") is True
            and [item.get("symbol") for item in data.get("results", [])] ==
                ([symbol] if retained else [])
            and [item.get("symbol") for item in data.get("rejected", [])] ==
                ([] if retained else [symbol]),
        "thesis_count_and_symbol": len(theses) == (1 if retained else 0)
            and (not retained or record.get("symbol") == symbol),
        "source_and_period": (candidate["source_url"].lower() in evidence_text
            and candidate["source_sha256"].lower() in evidence_text
            and candidate["period"].lower() in record_text) if retained else
            (candidate["source_url"].lower() in final or
             candidate["source_sha256"].lower() in final),
        "historical_preliminary_label": ("historical" in
            (record.get("title") or "").lower() and "preliminary" in
            (record.get("title") or "").lower()) if retained else True,
        "valuation_boundary": ("valuation" in record_text or "price" in record_text)
            if retained else ("valuation" in final or "price" in final or
                              "historical" in final),
        "review_date_safe": prior.future_or_unset(record.get("next_review_at")),
        "no_unexpected_state_or_trade": not state["alerts"] and
            all("trade" not in (name or "") for name in calls),
    }
    return checks, {"screen_tool_payload": payload, "tool_calls": calls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    case = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(RUN_ORDER),
                          "symbols": CASE_ORDER}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    candidates = {item["symbol"]: item for item in case["candidates"]}
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = workflow.FIXTURES = FIXTURES
    paths = [Path(__file__), PROTOCOL, CASE, SCRIPT,
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_sec_disclosure_screen_flash_v2.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH]
    paths += [HERE / item["local_path"] for item in case["candidates"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(panel_id=case["panel_id"], model=panel.MODEL,
                    pricing=panel.PRICING,
                    run_order=[f"FS-{symbol}-r{repeat}" for symbol, repeat in RUN_ORDER],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    source_boundary="three hashed SEC exhibits; one issuer per request; no live market data")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fintech-sec-screen-holdout-") as folder:
        for symbol, repeat in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"FS-{symbol}-r{repeat}"
            pilot = panel.PanelPilot(observation_id, args.template_db,
                                     args.gateway_binary, folder, True, spent)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                pilot.turn(prompt(candidates[symbol]))
                state = pilot.ledger_state()
                checks, extras = score(candidates[symbol], pilot, state)
                trace_checks, trace_details = panel.trace_checks(pilot)
                checks.update(trace_checks)
                extras["trace"] = trace_details
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                try:
                    state = pilot.ledger_state()
                except Exception:
                    pass
            finally:
                if process is not None:
                    base.stop_gateway(process, log)
            audit = audit_turns(pilot.turns)
            spent += pilot.cost
            result = {"observation_id": observation_id, "case_id": symbol,
                      "repetition": repeat, "workflow": "S",
                      "offline_frozen_adapter": True, "synthetic_source_data": False,
                      "status": "mechanical_pass" if error is None and checks and
                      all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2,
                                                                ensure_ascii=False) + "\n")
            ledger_db = pilot.home / "finance-tools.db"
            if ledger_db.is_file():
                shutil.copy2(ledger_db, directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "failed_checks": [key for key, value in checks.items() if not value],
                              "estimated_cost_usd": pilot.cost,
                              "cumulative_estimated_cost_usd": spent},
                             ensure_ascii=False), flush=True)
            if (error or audit["request_errors"] or audit["cost_uncertain_sequences"]
                    or audit["unpriced_sequences"]):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(RUN_ORDER), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
