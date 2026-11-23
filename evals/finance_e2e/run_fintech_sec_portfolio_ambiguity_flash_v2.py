#!/usr/bin/env python3
"""Prospective source-grounded portfolio issuer-aggregation ambiguity diagnostic."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_fintech_sec_portfolio_risk_flash_v1 as prior
import run_fintech_sec_screen_holdout_flash_v2 as screen_v2
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CASE = HERE / "fintech_sec_portfolio_ambiguity_panel_v2.json"
PROTOCOL = HERE / "FINTECH-SEC-PORTFOLIO-AMBIGUITY-PROTOCOL-v2.md"
CAP_USD = 0.04
CASE_ORDER = ("PA-DISTINCT", "PA-OVERLAP")
RUN_ORDER = [(case_id, repeat) for repeat in range(1, 6) for case_id in CASE_ORDER]


def preflight():
    _, screen_case = prior.preflight()
    case = json.loads(CASE.read_text())
    cases = {item["case_id"]: item for item in case["cases"]}
    if (case["panel_id"] != "FINTECH-SEC-PORTFOLIO-AMBIGUITY-v2"
            or case["source_symbols"] != ["COIN", "HOOD", "SQ"]
            or set(cases) != set(CASE_ORDER)):
        raise ValueError("prospective case mismatch")
    for item in cases.values():
        if (item["holdings_complete"] is not False
                or item["holdings_percent_known"] != {"COIN": 40, "HOOD": 30}
                or item["unknown_remainder_percent"] != 30
                or not item["clarification"]):
            raise ValueError("issuer-aggregation contrast mismatch")
    return case, cases, screen_case


def prompt(item):
    return (
        "Analyze one FICTIONAL long-only US equity portfolio as a historical "
        "research exercise, not a real account or trade recommendation. Known "
        "observations are percentages of TOTAL portfolio economic exposure: "
        "COIN 40%, HOOD 30%, plus an unspecified 30% of the total portfolio. "
        "The holdings map is incomplete. " + item["clarification"] + " "
        "A single issuer breaches policy only when its issuer-aggregated weight "
        "is GREATER THAN 50%; exactly 50% is not a breach. Call "
        "finance-tools__screen_stocks with market=US, symbols=[COIN,HOOD,SQ], "
        "require_complete=false to load frozen SEC-derived issuer fields. "
        "Inspect retained and rejected items; the screen's 20% revenue threshold "
        "is NOT the portfolio policy. Do not present a partial holdings map as "
        "complete or request an exact portfolio calculation. Explain what the "
        "single-issuer policy can and cannot establish, then combine at least "
        "two issuer-specific SEC facts into a useful supporting signal and "
        "counterpoint. Preserve company, period, units and source distinction. "
        "Do not invent holdings, equate position weights with crypto-factor "
        "exposure, infer return or valuation, recommend a trade, or create or "
        "modify ledger records. Case " + item["case_id"] + "."
    )


def score(item, pilot, state):
    checks, extras = prior.score(item, pilot, state)
    calls = extras["risk_tool_calls"]
    results = extras["risk_tool_results"]
    safe_calls = all(isinstance(call, dict) and call.get("holdings_complete") is False
                     for call in calls)
    refused = len(results) == len(calls) and all(
        isinstance(result, dict) and result.get("ok") is False
        and (result.get("quality") or {}).get("flags") == ["portfolio_incomplete"]
        and result.get("data") is None for result in results)
    checks["no_incomplete_risk_calculation"] = safe_calls and refused
    return checks, extras


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    case, cases, screen_case = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(RUN_ORDER),
                          "cases": CASE_ORDER, "source_symbols": case["source_symbols"]}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary, --output-dir required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = workflow.FIXTURES = prior.FIXTURES
    paths = [Path(__file__), PROTOCOL, CASE, prior.CASE, prior.PROTOCOL,
             prior.STOCK_SCRIPT, prior.PORTFOLIO_SCRIPT, prior.screen_v1.CASE,
             prior.screen_v1.SCRIPT, Path(prior.__file__),
             Path(prior.screen_v1.__file__), Path(screen_v2.__file__),
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH]
    paths += [HERE / source["local_path"] for source in screen_case["candidates"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(panel_id=case["panel_id"], model=panel.MODEL,
                    pricing=panel.PRICING, coordinator_max_tokens=screen_v2.MAX_TOKENS,
                    run_order=[f"{case_id}-r{repeat}" for case_id, repeat in RUN_ORDER],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    source_boundary="three historical SEC exhibits; fictional incomplete holdings; no exact risk score")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fintech-sec-portfolio-ambiguity-") as folder:
        for case_id, repeat in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"{case_id}-r{repeat}"
            pilot = screen_v2.OutputLimitPilot(observation_id, args.template_db,
                                               args.gateway_binary, folder, True, spent)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                pilot.turn(prompt(cases[case_id]))
                state = pilot.ledger_state()
                checks, extras = score(cases[case_id], pilot, state)
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
            result = {"observation_id": observation_id, "case_id": case_id,
                      "repetition": repeat, "workflow": "P", "holdings_synthetic": True,
                      "sec_source_data_synthetic": False,
                      "status": "mechanical_pass" if error is None and checks
                      and all(checks.values()) and audit["clean_completion"]
                      else "needs_review", "error": error, "checks": checks,
                      "runtime_audit": audit, "state": state, "extras": extras,
                      "turns": pilot.turns, "estimated_cost_usd": pilot.cost}
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
