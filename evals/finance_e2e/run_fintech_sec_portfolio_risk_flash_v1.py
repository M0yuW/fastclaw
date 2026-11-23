#!/usr/bin/env python3
"""Source-grounded fictional FinTech portfolio-risk panel, five repeats per case."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_fintech_sec_screen_holdout_flash_v1 as screen_v1
import run_fintech_sec_screen_holdout_flash_v2 as screen_v2
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_gateway import load_plugin, must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CASE = HERE / "fintech_sec_portfolio_risk_panel_v1.json"
PROTOCOL = HERE / "FINTECH-SEC-PORTFOLIO-RISK-PROTOCOL-v1.md"
FIXTURES = HERE / "workflow_fixtures_fintech_sec_portfolio_v1"
STOCK_SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
PORTFOLIO_SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/portfolio_analytics.py"
CAP_USD = 0.08
CASE_ORDER = ("PR-LIMIT", "PR-BREACH", "PR-INCOMPLETE")
RUN_ORDER = [(case_id, repeat) for repeat in range(1, 6)
             for case_id in CASE_ORDER]


def preflight():
    screen_case = screen_v1.preflight()
    case = json.loads(CASE.read_text())
    if (case["panel_id"] != "FINTECH-SEC-PORTFOLIO-RISK-v1" or
            case["source_symbols"] != ["COIN", "HOOD", "SQ"] or
            not all(path.is_file() for path in (STOCK_SCRIPT, PORTFOLIO_SCRIPT))):
        raise ValueError("frozen case or fixture mismatch")
    cases = {item["case_id"]: item for item in case["cases"]}
    if set(cases) != set(CASE_ORDER):
        raise ValueError("case set mismatch")
    with tempfile.TemporaryDirectory(prefix="fintech-sec-portfolio-preflight-") as folder:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(folder) / "finance.db"),
                           "finskillsPath": str(FIXTURES), "evaluationFixture": True})
        tenant = {"userId": "fintech-portfolio-preflight", "agentId": "finance-coordinator",
                  "sessionId": "preflight"}
        sourced = must_call(plugin, "screen_stocks", {
            "market": "US", "symbols": case["source_symbols"],
            "require_complete": False}, tenant)
        if ({item["symbol"] for item in sourced["results"]} != {"COIN", "HOOD"}
                or {item["symbol"] for item in sourced["rejected"]} != {"SQ"}
                or sourced.get("offline_frozen_adapter") is not True):
            raise ValueError("SEC source adapter batch mismatch")
        for case_id in CASE_ORDER[:2]:
            item = cases[case_id]
            result = must_call(plugin, "portfolio_risk", {
                "holdings": item["holdings_percent"], "weight_unit": "percent",
                "holdings_complete": True, "view": "concentration"}, tenant)
            expected = item["oracle"]
            if (result["largest_holding"] != expected["largest_holding"] or
                    result["largest_weight_pct"] != expected["largest_weight_pct"] or
                    result["limit_breached"] != expected["limit_breached"] or
                    result["herfindahl_index"] != expected["herfindahl_index"]):
                raise ValueError(f"portfolio oracle mismatch for {case_id}")
    return case, screen_case


def prompt(item):
    if item["holdings_complete"]:
        holding_text = ", ".join(f"{symbol} {weight}%" for symbol, weight in
                                 item["holdings_percent"].items()) + ". The list is complete."
    else:
        holding_text = (", ".join(f"{symbol} {weight}%" for symbol, weight in
                                  item["holdings_percent_known"].items()) +
                        f", plus {item['unknown_remainder_percent']}% of the total portfolio "
                        "in unspecified long-only holdings. The list is incomplete.")
    return (
        "Analyze one FICTIONAL long-only US equity portfolio as a historical research "
        "exercise, not a real account or trade recommendation. Known weights are "
        "percentages of TOTAL economic exposure: " + holding_text + " The policy "
        "flags a single holding only when its weight is GREATER THAN 50%; exactly "
        "50% is at the limit, not a breach. Call finance-tools__screen_stocks with "
        "market=US, symbols=[COIN,HOOD,SQ], require_complete=false to load the "
        "frozen SEC-derived issuer fields. Inspect BOTH retained and rejected "
        "items; the screen's 20% revenue threshold is NOT this portfolio policy. "
        "For a complete portfolio, call finance-tools__portfolio_risk with the "
        "exact weights, weight_unit=percent, holdings_complete=true and "
        "view=concentration. For incomplete holdings, do not pretend the list "
        "is complete or submit an exact calculation to the risk tool. Report "
        "what is logically knowable and what remains unknown. Explain the "
        "concentration result or bound, then combine at least two issuer-specific "
        "SEC facts into a useful supporting signal and counterpoint. Preserve "
        "company, period, units and source distinction. Do not equate portfolio "
        "position weights with quantified crypto-factor exposure, or infer "
        "valuation, future return or a trade from these materials. Do not "
        "create or modify any ledger records. Case " + item["case_id"] + "."
    )


def payloads(pilot, name, kind):
    found = []
    for turn in pilot.turns:
        trace = ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []
        for entry in trace:
            if entry.get("type") == kind and entry.get("name") == name:
                try:
                    found.append(json.loads(entry.get("arguments" if kind == "tool_call"
                                                       else "result") or "{}"))
                except json.JSONDecodeError:
                    found.append(None)
    return found


def score(item, pilot, state):
    screens = payloads(pilot, "finance-tools__screen_stocks", "tool_result")
    screen = next((p.get("data") for p in screens if isinstance(p, dict) and p.get("ok")), {})
    risk_calls = payloads(pilot, "finance-tools__portfolio_risk", "tool_call")
    risk_results = payloads(pilot, "finance-tools__portfolio_risk", "tool_result")
    names = [name for turn in pilot.turns for name in turn["tool_calls"]]
    checks = {
        "sec_source_tool_called": "finance-tools__screen_stocks" in names,
        "source_locked_batch": bool(screen) and screen.get("offline_frozen_adapter") is True
            and screen.get("synthetic") is False
            and {p.get("symbol") for p in screen.get("results", [])} == {"COIN", "HOOD"}
            and {p.get("symbol") for p in screen.get("rejected", [])} == {"SQ"},
        "no_ledger_mutation_or_trade": not state["theses"] and not state["alerts"]
            and all("trade" not in (name or "") for name in names),
    }
    if item["holdings_complete"]:
        expected = item["oracle"]
        checks["risk_tool_called_with_exact_holdings"] = any(
            isinstance(p, dict) and p.get("holdings") == item["holdings_percent"]
            and p.get("weight_unit") == "percent" and p.get("holdings_complete") is True
            and p.get("view") == "concentration" for p in risk_calls)
        checks["risk_tool_oracle"] = any(
            isinstance(p, dict) and p.get("ok") is True and
            (p.get("data") or {}).get("fixture_id") == "fintech-sec-portfolio-v1" and
            (p.get("data") or {}).get("largest_holding") == expected["largest_holding"] and
            (p.get("data") or {}).get("largest_weight_pct") == expected["largest_weight_pct"] and
            (p.get("data") or {}).get("limit_breached") == expected["limit_breached"] and
            (p.get("data") or {}).get("herfindahl_index") == expected["herfindahl_index"]
            for p in risk_results)
    else:
        checks["no_incomplete_risk_calculation"] = not risk_calls
    return checks, {"screen_tool_results": screens, "risk_tool_calls": risk_calls,
                    "risk_tool_results": risk_results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    case, screen_case = preflight()
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
    cases = {item["case_id"]: item for item in case["cases"]}
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = workflow.FIXTURES = FIXTURES
    paths = [Path(__file__), PROTOCOL, CASE, screen_v1.CASE, STOCK_SCRIPT,
             PORTFOLIO_SCRIPT, screen_v1.SCRIPT, Path(screen_v1.__file__),
             Path(screen_v2.__file__), HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
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
                    source_boundary="three real SEC exhibits; fictional holdings; offline deterministic risk calculator")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fintech-sec-portfolio-panel-") as folder:
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
                      "repetition": repeat, "workflow": "P",
                      "holdings_synthetic": True, "sec_source_data_synthetic": False,
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
