#!/usr/bin/env python3
"""Run the frozen independent-source decision-hold case with Flash only."""

import argparse
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import run_finance_conflict_guard_v1 as guard
import run_finance_conflict_sources as sources
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_gateway import create_ephemeral_key, load_plugin
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, prepare_home, sha256

MODEL = "deepseek/deepseek-v4-flash"
PRICING = {MODEL: {"input_per_million": 0.14, "output_per_million": 0.28,
                   "cache_read_per_million": 0.0028}}
CAP_USD = 0.03


class FlashPilot(base.Pilot):
    def __init__(self, case_id, template_db, binary, temp_root, spent_so_far):
        self.case_id = case_id
        self.home = prepare_home(template_db, binary, temp_root)
        base.configure(self.home, True)
        with sqlite3.connect(self.home / "fastclaw.db") as database:
            row = database.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
            agent = json.loads(row[0])
            agent["model"] = MODEL
            database.execute("UPDATE agents SET config=? WHERE id=?",
                             (json.dumps(agent), AGENT_ID))
        self.token, user_id = create_ephemeral_key(self.home / "fastclaw.db", AGENT_ID)
        self.tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "pilot-seed"}
        self.finance = load_plugin().FinanceToolsPlugin()
        self.finance.initialize({"stateDbPath": str(self.home / "finance-tools.db"),
                                 "finskillsPath": str(workflow.FIXTURES),
                                 "evaluationFixture": True})
        self.synthetic = True
        self.spent_before = spent_so_far
        self.turns = []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    sources.source_packet()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL = MODEL
    base.PRICING = PRICING
    base.CAP_USD = CAP_USD
    base.FIXTURES = workflow.FIXTURES
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_conflict_guard_v1.py",
             HERE / "run_finance_conflict_sources.py", HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_v2.py", HERE / "run_thesis_event_panel.py",
             HERE / "run_thesis_event_gateway.py", *sources.SOURCE_FILES, PLUGIN_PATH,
             ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go"]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=MODEL, pricing=PRICING,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    run_order=["W02GF-r1", "W02GF-r2"])
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-conflict-flash-") as temp_root:
        for run_id in manifest["run_order"]:
            if spent >= CAP_USD:
                break
            pilot = FlashPilot(run_id, args.template_db, args.gateway_binary,
                               temp_root, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, refs, error = None, {}, [], None
            try:
                state, checks, refs = guard.run_case(pilot)
                for turn in pilot.turns:
                    calls = turn["response"]["fastclaw"]["model_calls"]
                    if not calls or any(call["model"] != MODEL for call in calls):
                        raise RuntimeError("non-Flash inner model call")
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                base.stop_gateway(process, log)
            spent += pilot.cost
            result = {"run_id": run_id, "status": "mechanical_pass" if error is None and
                      all(checks.values()) else "needs_review", "error": error,
                      "checks": checks, "sources": refs, "state": state,
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
