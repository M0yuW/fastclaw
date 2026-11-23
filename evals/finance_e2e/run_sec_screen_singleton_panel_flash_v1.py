#!/usr/bin/env python3
"""Four historical SEC single-company screens, five isolated Flash repeats each."""

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


CASE = HERE / "sec_disclosure_screen_singleton_panel_v1.json"
PROTOCOL = HERE / "SEC-SCREEN-SINGLETON-PANEL-PROTOCOL-v1.md"
FIXTURES = HERE / "workflow_fixtures_sec_screen_panel_v1"
SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
CAP_USD = 0.08
REPETITIONS = 5
CASE_ORDER = ("AMD", "NVDA", "INTC", "NKE")
RUN_ORDER = [(symbol, repeat) for repeat in range(1, REPETITIONS + 1)
             for symbol in CASE_ORDER]
ORACLE = {"AMD": True, "NVDA": True, "INTC": False, "NKE": False}
EPISODE_ORACLE = {
    "AMD": ("FSEC-AMD-02", {"AMD-Q3-REV": "6819", "AMD-Q3-GM": "50", "AMD-Q3-GAME": "462"}),
    "NVDA": ("FSEC-NVDA-02", {"NVDA-Q2-REV": "30040", "NVDA-Q2-GM": "75.1", "NVDA-Q2-DC": "26300"}),
    "INTC": ("FSEC-INTC-03", {"INTC-Q3-REV": "13300", "INTC-Q3-GM": "15.0", "INTC-Q3-RESTRUCT": "2800"}),
    "NKE": ("FSEC-NKE-02", {"NKE-Q2FY25-REV": "12354", "NKE-Q2FY25-GM": "43.6", "NKE-Q2FY25-DIGITAL": "-21"}),
}


def preflight():
    case = json.loads(CASE.read_text())
    if case["panel_id"] != "SEC-DISCLOSURE-SINGLETON-PANEL-v1" or not SCRIPT.is_file():
        raise ValueError("frozen panel or adapter absent")
    candidates = {item["symbol"]: item for item in case["candidates"]}
    if set(candidates) != set(CASE_ORDER):
        raise ValueError("candidate set differs from frozen panel")
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    episodes = {item["id"]: item for item in json.loads((HERE / "evidence.json").read_text())["episodes"]}
    for symbol, candidate in candidates.items():
        source = lock[candidate["source_id"]]
        if (candidate["source_url"] != source["url"] or
                candidate["source_sha256"] != source["sha256"] or
                sha256(HERE / source["local_path"]) != source["sha256"]):
            raise ValueError(f"source lock mismatch for {symbol}")
        episode_id, expected = EPISODE_ORACLE[symbol]
        facts = {fact["id"]: fact["value"] for fact in episodes[episode_id]["facts"]}
        if episodes[episode_id]["source_id"] != candidate["source_id"] or any(
                facts.get(key) != value for key, value in expected.items()):
            raise ValueError(f"independent episode fact mismatch for {symbol}")
    with tempfile.TemporaryDirectory(prefix="sec-screen-singleton-preflight-") as folder:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(folder) / "finance.db"),
                           "finskillsPath": str(FIXTURES), "evaluationFixture": True})
        tenant = {"userId": "sec-screen-preflight", "agentId": "finance-coordinator",
                  "sessionId": "preflight"}
        for symbol in CASE_ORDER:
            data = must_call(plugin, "screen_stocks", {
                "market": "US", "symbols": [symbol], "require_complete": False}, tenant)
            if ([item["symbol"] for item in data["results"]] !=
                    ([symbol] if ORACLE[symbol] else []) or
                    [item["symbol"] for item in data["rejected"]] !=
                    ([] if ORACLE[symbol] else [symbol])):
                raise ValueError(f"deterministic screen mismatch for {symbol}")
    return case


def prompt(candidate):
    symbol = candidate["symbol"]
    return (
        "Run a historical disclosure-only candidate-research workflow, not a live "
        "investment recommendation. Call finance-tools__screen_stocks for US symbol "
        + symbol + " with require_complete=false. This case's frozen offline adapter "
        "uses only the disclosed GAAP gross margin >=40% and reported revenue YoY "
        ">=0%; it does not use the seven-factor live market-data completeness gate. "
        "Read retained and rejected results, exact failed criteria, source URL and full "
        "SHA-256, filing date, reporting period, units and countervailing risks. "
        "If retained, save exactly one HISTORICAL PRELIMINARY research thesis with "
        "the full SEC URL/hash in structured evidence, material reported numbers, "
        "a risk and the missing price/valuation boundary. If rejected, save no thesis "
        "and explain why. Do not trade, call live market tools, imply these issuers "
        "were ranked on a common date, or turn a narrow screen into an investment "
        "recommendation. Omit next_review_at unless it is after the current run date."
    )


def score(candidate, pilot, state):
    symbol = candidate["symbol"]
    retained = ORACLE[symbol]
    theses = [item["thesis"] for item in state["theses"]]
    record = theses[0] if len(theses) == 1 else {}
    record_text = json.dumps(record, ensure_ascii=False).lower()
    evidence_text = json.dumps(record.get("evidence") or [], ensure_ascii=False).lower()
    final = workflow.final_text(pilot).lower()
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    payload = prior.tool_screen_data(pilot)
    data = payload.get("data") if isinstance(payload, dict) and payload.get("ok") else {}
    expected_results = [symbol] if retained else []
    expected_rejected = [] if retained else [symbol]
    reported = candidate["reported"]
    revenue = str(reported.get("gaap_revenue_usd_million", reported.get("gaap_revenue_usd_million_rounded")))
    margin = str(reported["gaap_gross_margin_percent"])
    numerical_text = (record_text if retained else final).replace(",", "")
    core_values = (revenue in numerical_text and margin in numerical_text
                   and str(reported["revenue_yoy_percent"]) in numerical_text) if retained else (
                       margin in numerical_text and
                       str(reported["revenue_yoy_percent"]) in numerical_text)
    checks = {
        "screen_called": "finance-tools__screen_stocks" in calls,
        "source_locked_tool_result": bool(data) and data.get("synthetic") is False
            and data.get("offline_frozen_adapter") is True
            and [item.get("symbol") for item in data.get("results", [])] == expected_results
            and [item.get("symbol") for item in data.get("rejected", [])] == expected_rejected,
        "thesis_count_and_symbol": len(theses) == (1 if retained else 0)
            and (not retained or record.get("symbol") == symbol),
        "source_and_period_retained": (candidate["source_url"].lower() in evidence_text
            and candidate["source_sha256"].lower() in evidence_text
            and candidate["period"].lower() in record_text) if retained else
            (candidate["source_url"].lower() in final or candidate["source_sha256"].lower() in final),
        "core_values_reported": core_values,
        "historical_preliminary_label": ("historical" in (record.get("title") or "").lower()
            and "preliminary" in (record.get("title") or "").lower()) if retained else True,
        "valuation_boundary": ("valuation" in record_text or "price" in record_text)
            if retained else ("valuation" in final or "price" in final or "historical" in final),
        "review_date_safe": prior.future_or_unset(record.get("next_review_at")),
        "no_unexpected_state_or_trade": not state["alerts"] and
            all("trade" not in (name or "") for name in calls),
    }
    if not retained:
        failures = data["rejected"][0].get("failed_criteria", []) if data else []
        checks["rejection_explained"] = bool(failures) and (
            "revenue" in final or "sales" in final) and (
            "gaap_gross_margin_below_threshold" not in failures or
            any(term in final for term in ("margin", "gross", "gm")))
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
    paths = [Path(__file__), PROTOCOL, CASE, SCRIPT, HERE / "evidence.json",
             HERE / "source-lock.json", HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_sec_disclosure_screen_flash_v2.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH]
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    paths += [HERE / lock[item["source_id"]]["local_path"] for item in case["candidates"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(panel_id=case["panel_id"], model=panel.MODEL, pricing=panel.PRICING,
                    run_order=[f"S-{symbol}-r{repeat}" for symbol, repeat in RUN_ORDER],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    source_boundary="four cached SEC exhibits; one issuer per request; no live market data")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="sec-screen-singleton-panel-") as folder:
        for symbol, repeat in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"S-{symbol}-r{repeat}"
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
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            ledger_db = pilot.home / "finance-tools.db"
            if ledger_db.is_file():
                shutil.copy2(ledger_db, directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id, "status": result["status"],
                              "error": error, "failed_checks": [key for key, value in checks.items() if not value],
                              "estimated_cost_usd": pilot.cost,
                              "cumulative_estimated_cost_usd": spent}, ensure_ascii=False), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(RUN_ORDER), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
