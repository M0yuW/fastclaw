#!/usr/bin/env python3
"""Independent post-fix Flash rerun of the 16-case exploratory panel."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_16_flash_v1 as original
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
import s1_candidate_case_v2 as s1
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns

CAP_USD = 0.12
ORIGINAL_FIXTURES = workflow.FIXTURES


def preflight():
    original.preflight()
    fixture = s1.FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
    if not fixture.is_file():
        raise FileNotFoundError(fixture)
    with tempfile.TemporaryDirectory(prefix="finance-16-v2-preflight-") as root:
        from run_thesis_event_gateway import load_plugin, must_call
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(root) / "finance-tools.db"),
                           "finskillsPath": str(s1.FIXTURES), "evaluationFixture": True})
        tenant = {"userId": "v2-preflight", "agentId": "v2-preflight", "sessionId": "v2"}
        data = must_call(plugin, "screen_stocks", {
            "market": "US", "symbols": ["FICC", "FICD"], "require_complete": True}, tenant)
        if not data:
            raise ValueError("S1 v2 screen fixture returned no data")


def portfolio_guard_results(pilot):
    results = []
    for turn in pilot.turns:
        for event in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []:
            if event.get("type") != "tool_result" or event.get("name") != "finance-tools__portfolio_risk":
                continue
            raw = event.get("result")
            if raw is None:
                raw = event.get("content")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except json.JSONDecodeError:
                    pass
            results.append(raw)
    return results


def portfolio_incomplete_rejected(item):
    return (isinstance(item, dict) and item.get("ok") is False and
            item.get("data") is None and
            any(isinstance(error, dict) and error.get("code") == "portfolio_incomplete"
                for error in item.get("errors") or []))


def run_case(case_id, pilot):
    if case_id == "S1":
        pilot.turn(s1.prompt())
        state = pilot.ledger_state()
        calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
        return state, s1.score(state, calls), {"oracle_version": "S1-v2"}
    if case_id == "P4":
        # An unknown exact holding weight does not imply that every policy
        # question is unknowable. Keep this guidance general: the agent must
        # derive any bound itself without being given the conclusion.
        text, _, _, _ = original.PORTFOLIO[case_id]
        pilot.turn(
            "This is a synthetic portfolio-risk diagnostic, not a live account. "
            "Available holdings: " + text + ". The single-holding concentration "
            "policy is breached only when a weight exceeds 50%; exactly 50% is "
            "at the limit. Use finance-tools__portfolio_risk with "
            "view=concentration only if the complete portfolio is known. "
            "Distinguish an uncomputable exact portfolio statistic from a "
            "policy conclusion that may be provable by a bound on the unknown "
            "holdings. State assumptions explicitly; do not invent a missing "
            "weight, trade, change holdings, or create ledger records. Case P4."
        )
        state = pilot.ledger_state()
        payloads = original.tool_payloads(pilot, "finance-tools__portfolio_risk")
        final = original.normalized_numbers(original.final_text(pilot)).lower()
        checks = {
            "no_ledger_mutation": not state["theses"] and not state["alerts"],
            "no_incomplete_calculation": not payloads,
            "uncertainty_explained": any(word in final for word in
                                         ("missing", "unknown", "incomplete", "cannot", "insufficient")),
        }
        extras = {"expected_holdings": None, "expected_limit_breached": False,
                  "bounded_reasoning_prompt": True}
        agent_preflight = checks.pop("no_incomplete_calculation")
        results = portfolio_guard_results(pilot)
        # A blocked invalid call is a safe outcome, but the model's attempt is
        # retained separately so tool-layer protection is not credited to it.
        checks["safe_incomplete_handling"] = agent_preflight or (
            bool(results) and all(portfolio_incomplete_rejected(item) for item in results))
        extras["agent_avoided_incomplete_call"] = agent_preflight
        extras["portfolio_tool_results"] = results
        return state, checks, extras
    function, _ = original.FUNCTIONS[case_id[0]]
    return function(case_id, pilot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    preflight()
    if args.preflight_only:
        print(json.dumps({"cases": original.CASES, "preflight": "ok"}))
        return
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_workflow_16_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "s1_candidate_case_v2.py", HERE / "workflow_runtime_audit_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "test_thesis_event_integration.py", HERE / "evidence.json",
             HERE / "source-lock.json", PLUGIN_PATH,
             *ORIGINAL_FIXTURES.rglob("*.py"), *s1.FIXTURES.rglob("*.py")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    case_order=original.CASES,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD, observation_count_planned=16,
                    source_boundary="SEC cases source-locked; other cases synthetic",
                    changes_from_v1="S1 case and oracle revised; P4 tool guard and outcome scoring; runtime JSON recovery and audit")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-16-flash-v2-") as temp_root:
        for case_id in original.CASES:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            synthetic = case_id[0] != "E"
            fixture = s1.FIXTURES if case_id == "S1" else ORIGINAL_FIXTURES
            base.FIXTURES = workflow.FIXTURES = fixture
            pilot = panel.PanelPilot(case_id, args.template_db, args.gateway_binary,
                                     temp_root, synthetic, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = run_case(case_id, pilot)
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
                base.stop_gateway(process, log)
            audit = audit_turns(pilot.turns)
            spent += pilot.cost
            result = {"case_id": case_id, "workflow": case_id[0],
                      "synthetic_tool_fixture": synthetic,
                      "status": "mechanical_pass" if error is None and checks and
                      all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / case_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"case_id": case_id, "status": result["status"],
                              "error": error, "failed_checks": [key for key, value in checks.items() if not value],
                              "runtime_audit": audit, "estimated_cost_usd": pilot.cost},
                             ensure_ascii=False), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": spent}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
