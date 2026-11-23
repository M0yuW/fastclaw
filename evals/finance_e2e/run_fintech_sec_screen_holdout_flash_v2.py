#!/usr/bin/env python3
"""New full FinTech SEC screen arm with only coordinator maxTokens increased."""

import argparse
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import run_fintech_sec_screen_holdout_flash_v1 as v1
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


PROTOCOL = HERE / "FINTECH-SEC-SCREEN-HOLDOUT-OUTPUT-LIMIT-v2.md"
MAX_TOKENS = 5000


class OutputLimitPilot(panel.PanelPilot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        with sqlite3.connect(self.home / "fastclaw.db") as db:
            row = db.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
            agent = json.loads(row[0])
            if agent.get("maxTokens") != 2500:
                raise ValueError("unexpected baseline output limit")
            agent["maxTokens"] = MAX_TOKENS
            db.execute("UPDATE agents SET config=? WHERE id=?",
                       (json.dumps(agent), AGENT_ID))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    case = v1.preflight()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    candidates = {item["symbol"]: item for item in case["candidates"]}
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, v1.CAP_USD
    base.FIXTURES = workflow.FIXTURES = v1.FIXTURES
    paths = [Path(__file__), PROTOCOL, Path(v1.__file__), v1.PROTOCOL,
             v1.CASE, v1.SCRIPT, HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_sec_disclosure_screen_flash_v2.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH]
    paths += [HERE / item["local_path"] for item in case["candidates"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(panel_id=case["panel_id"] + "-OUTPUT-LIMIT-v2",
                    parent_panel_id=case["panel_id"], model=panel.MODEL,
                    pricing=panel.PRICING,
                    run_order=[f"FS2-{symbol}-r{repeat}" for symbol, repeat in v1.RUN_ORDER],
                    coordinator_max_tokens=MAX_TOKENS,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=v1.CAP_USD,
                    source_boundary="same three hashed SEC exhibits as v1; no live market data")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fintech-sec-screen-output-v2-") as folder:
        for symbol, repeat in v1.RUN_ORDER:
            if spent >= v1.CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"FS2-{symbol}-r{repeat}"
            pilot = OutputLimitPilot(observation_id, args.template_db,
                                     args.gateway_binary, folder, True, spent)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                pilot.turn(v1.prompt(candidates[symbol]))
                state = pilot.ledger_state()
                checks, extras = v1.score(candidates[symbol], pilot, state)
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
                      "planned": len(v1.RUN_ORDER), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
