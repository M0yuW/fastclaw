#!/usr/bin/env python3
"""Five fresh Flash observations of each of 16 frozen finance workflow cases."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_16_flash_v2 as cases
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
import s1_candidate_case_v2 as s1
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns

CAP_USD = 0.12
REPETITIONS = 5
CASE_ORDER = cases.original.CASES
RUN_ORDER = [(case_id, repetition) for repetition in range(1, REPETITIONS + 1)
             for case_id in CASE_ORDER]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    cases.preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(RUN_ORDER),
                          "case_order": CASE_ORDER, "repetitions": REPETITIONS}))
        return
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    paths = [Path(__file__), HERE / "run_finance_workflow_16_flash_v2.py",
             HERE / "run_finance_workflow_16_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "s1_candidate_case_v2.py", HERE / "workflow_runtime_audit_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "test_thesis_event_integration.py", HERE / "evidence.json",
             HERE / "source-lock.json", PLUGIN_PATH,
             *cases.ORIGINAL_FIXTURES.rglob("*.py"), *s1.FIXTURES.rglob("*.py")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=[f"{case_id}-r{repetition}" for case_id, repetition in RUN_ORDER],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD, observation_count_planned=len(RUN_ORDER),
                    sampling="five new independent sessions and ledgers per frozen case; no v2 rerun results counted",
                    source_boundary="SEC cases source-locked; other cases synthetic")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-reliability-flash-") as temp_root:
        for case_id, repetition in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"{case_id}-r{repetition}"
            synthetic = case_id[0] != "E"
            fixture = s1.FIXTURES if case_id == "S1" else cases.ORIGINAL_FIXTURES
            base.FIXTURES = workflow.FIXTURES = fixture
            pilot = panel.PanelPilot(observation_id, args.template_db,
                                     args.gateway_binary, temp_root, synthetic, spent)
            state, checks, extras, error = None, {}, {}, None
            process, log = base.start_gateway(pilot.home)
            try:
                state, checks, extras = cases.run_case(case_id, pilot)
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
            result = {"observation_id": observation_id, "case_id": case_id,
                      "repetition": repetition, "workflow": case_id[0],
                      "synthetic_tool_fixture": synthetic,
                      "status": "mechanical_pass" if error is None and checks and
                      all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "failed_checks": [key for key, value in checks.items() if not value],
                              "runtime_clean": audit["clean_completion"],
                              "estimated_cost_usd": pilot.cost,
                              "cumulative_estimated_cost_usd": spent},
                             ensure_ascii=False), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(RUN_ORDER), "estimated_cost_usd": spent},
                     ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
