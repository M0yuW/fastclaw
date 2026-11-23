#!/usr/bin/env python3
"""Flash-only, six-attempt panel for three distinct finance workflows."""

import argparse
import json
import shutil
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path

import run_finance_conflict_guard_flash_v1 as flash
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_gateway import create_ephemeral_key, load_plugin
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, prepare_home, sha256

MODEL = flash.MODEL
PRICING = flash.PRICING
CAP_USD = 0.06
RUN_ORDER = ["W01F-r1", "W03F-r1", "W04F-r1",
             "W04F-r2", "W03F-r2", "W01F-r2"]
WORKFLOWS = {"W01": (workflow.run_w01, False),
             "W03": (workflow.run_w03, True),
             "W04": (workflow.run_w04, True)}


class PanelPilot(base.Pilot):
    def __init__(self, case_id, template_db, binary, temp_root, synthetic, spent_so_far):
        self.case_id = case_id
        self.home = prepare_home(template_db, binary, temp_root)
        base.configure(self.home, synthetic)
        with sqlite3.connect(self.home / "fastclaw.db") as database:
            row = database.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
            agent = json.loads(row[0])
            agent["model"] = MODEL
            database.execute("UPDATE agents SET config=? WHERE id=?",
                             (json.dumps(agent), AGENT_ID))
        self.token, user_id = create_ephemeral_key(self.home / "fastclaw.db", AGENT_ID)
        self.tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "panel-seed"}
        self.finance = load_plugin().FinanceToolsPlugin()
        config = {"stateDbPath": str(self.home / "finance-tools.db")}
        if synthetic:
            config.update(finskillsPath=str(workflow.FIXTURES), evaluationFixture=True)
        self.finance.initialize(config)
        self.synthetic = synthetic
        self.spent_before = spent_so_far
        self.turns = []


def trace_checks(pilot):
    calls, results, models = [], [], []
    for turn in pilot.turns:
        response = turn.get("response") or {}
        metadata = response.get("fastclaw") or {}
        trace = metadata.get("trace") or []
        calls.extend(item["id"] for item in trace if item.get("type") == "tool_call")
        results.extend(item["id"] for item in trace if item.get("type") == "tool_result")
        models.extend(call.get("model") for call in metadata.get("model_calls") or [])
    return {
        "flash_only": bool(models) and set(models) == {MODEL},
        "tool_trace_complete": bool(calls) and Counter(calls) == Counter(results),
        "usage_priced": bool(pilot.turns) and all(turn["priced_usage"] for turn in pilot.turns),
        "cost_positive": pilot.cost > 0,
    }, {"model_calls": len(models), "tool_calls": len(calls),
        "tool_results": len(results), "models": sorted(set(models))}


def source_checks(workflow_id, state):
    if workflow_id != "W01":
        return {}, {}
    expected = {}
    for episode_id, facts in [
        ("FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-GM", "NVDA-Q2-DC"]),
        ("FSEC-NVDA-03", ["NVDA-Q4-REV", "NVDA-Q4-GM", "NVDA-Q4-DC"]),
    ]:
        event, _ = base.event_from_episode(episode_id, facts)
        expected[event["external_id"]] = event
    alerts = state["alerts"]
    reviews = state["theses"][0]["reviews"] if state["theses"] else []
    observed = {alert["event"]["external_id"]: alert for alert in alerts}
    check_alerts = set(observed) == set(expected) and all(
        observed[key]["event"]["sources"] == item["sources"]
        and observed[key]["event"]["observed_metrics"] == item["observed_metrics"]
        for key, item in expected.items()
    )
    alert_by_id = {alert["id"]: alert for alert in alerts}
    check_reviews = len(reviews) == 2 and all(
        review["alert_id"] in alert_by_id
        and review["event"]["sources"] == alert_by_id[review["alert_id"]]["event"]["sources"]
        for review in reviews
    )
    return (
        {"sec_packet_sources_and_values_exact": check_alerts,
         "review_source_links_exact": check_reviews},
        {"expected_source_ids": sorted(expected)},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    workflow.preflight()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = MODEL, PRICING, CAP_USD
    base.FIXTURES = workflow.FIXTURES
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_workflow_v2.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_conflict_guard_flash_v1.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "test_thesis_event_integration.py", HERE / "evidence.json",
             HERE / "source-lock.json", PLUGIN_PATH,
             ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go",
             *workflow.FIXTURES.rglob("*.py"), workflow.CONFLICT]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=MODEL, pricing=PRICING, run_order=RUN_ORDER,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-flash-panel-") as temp_root:
        for run_id in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            workflow_id = run_id[:3]
            function, synthetic = WORKFLOWS[workflow_id]
            pilot = PanelPilot(run_id, args.template_db, args.gateway_binary,
                               temp_root, synthetic, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = function(pilot)
                trace, trace_details = trace_checks(pilot)
                source, source_details = source_checks(workflow_id, state)
                checks.update(trace)
                checks.update(source)
                extras.update(trace=trace_details, source_audit=source_details)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                base.stop_gateway(process, log)
            spent += pilot.cost
            result = {"run_id": run_id, "workflow": workflow_id,
                      "synthetic_tool_fixture": synthetic,
                      "status": "mechanical_pass" if error is None and all(checks.values()) else "needs_review",
                      "error": error, "checks": checks, "state": state, "extras": extras,
                      "turns": pilot.turns, "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / run_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"run_id": run_id, "status": result["status"],
                              "error": error, "checks": checks,
                              "estimated_cost_usd": pilot.cost}, ensure_ascii=False), flush=True)
            if error or any(not turn["priced_usage"] for turn in pilot.turns):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": spent}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
