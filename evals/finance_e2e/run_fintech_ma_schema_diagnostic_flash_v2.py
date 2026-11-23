#!/usr/bin/env python3
"""Five same-case Mastercard repeats after causal-claim tool-schema repair."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import run_fresh_fintech_sec_panel_flash_v1 as parent
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


PROTOCOL = HERE / "FINTECH-MA-SCHEMA-RECOVERY-DIAGNOSTIC-v2.md"
CASE_ID = "FINTECH-MA-GAAP-ADJ"
CAP_USD = 0.05
RESERVE_NEXT_USD = 0.01
REPEATS = 5
SEED = 2244


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    parent.configure_common()
    preflight = parent.source_preflight.verify()
    case = next(case for case in json.loads(parent.CORPUS.read_text())["cases"]
                if case["case_id"] == CASE_ID)
    order = list(range(1, REPEATS + 1))
    random.Random(SEED).shuffle(order)
    if args.preflight_only:
        if args.template_db or args.gateway_binary:
            if not all((args.template_db, args.gateway_binary)):
                parser.error("provide both --template-db and --gateway-binary")
            parent.common.dry_run_tool_setup([case], args.template_db,
                                             args.gateway_binary)
        print(json.dumps({"preflight": "ok", "source_preflight": preflight["preflight"],
                          "case_id": CASE_ID, "repeats": REPEATS, "order": order,
                          "tool_setup": "ok" if args.template_db else "not_requested"}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    parent.common.base.MODEL, parent.common.base.PRICING, parent.common.base.CAP_USD = (
        parent.common.panel.MODEL, parent.common.panel.PRICING, CAP_USD)
    paths = [Path(__file__), PROTOCOL, parent.CORPUS,
             Path(parent.source_preflight.__file__),
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_fresh_fintech_sec_panel_flash_v1.py",
             HERE / "run_fresh_sec_multiissuer_flash_v1.py",
             HERE / "run_guarded_sec_review_pilot_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH,
             ROOT / "plugins/finance-tools/accounting_lineage.py",
             ROOT / "internal/policy/defaults.go"]
    paths += [HERE / case[period]["local_path"] for period in ("baseline", "event")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=parent.common.panel.MODEL,
                    pricing=parent.common.panel.PRICING,
                    case_id=CASE_ID, run_order=order, random_seed=SEED,
                    repeats_per_case=REPEATS, policy="finance-review-only",
                    diagnostic_not_holdout=True,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fintech-ma-schema-v2-") as root:
        for repeat in order:
            if spent + RESERVE_NEXT_USD > CAP_USD:
                print("STOP: conservative estimated-spend reserve reached", flush=True)
                break
            observation_id = f"{CASE_ID}-r{repeat}"
            pilot = parent.common.panel.PanelPilot(
                observation_id, args.template_db, args.gateway_binary,
                root, False, spent)
            parent.common.set_review_only(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = parent.common.base.start_gateway(pilot.home)
                state, checks, extras = parent.common.run_case(case, pilot)
                trace_checks, trace_details = parent.common.panel.trace_checks(pilot)
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
                    parent.common.base.stop_gateway(process, log)
            runtime_audit = parent.common.audit_turns(pilot.turns)
            spent += pilot.cost
            result = {
                "observation_id": observation_id, "case_id": CASE_ID,
                "repeat": repeat, "workflow": "guarded_ma_schema_recovery_diagnostic",
                "status": ("mechanical_pass" if error is None and checks
                           and all(checks.values()) and runtime_audit["clean_completion"]
                           else "needs_review"),
                "error": error, "checks": checks, "runtime_audit": runtime_audit,
                "state": state, "extras": extras, "turns": pilot.turns,
                "estimated_cost_usd": pilot.cost,
            }
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            ledger = pilot.home / "finance-tools.db"
            if ledger.is_file():
                shutil.copy2(ledger, directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"],
                              "failed_checks": [key for key, value in checks.items()
                                                if not value],
                              "error": error, "cost": pilot.cost,
                              "cumulative_cost": spent}), flush=True)
            if (error or runtime_audit["request_errors"]
                    or runtime_audit["cost_uncertain_sequences"]
                    or runtime_audit["unpriced_sequences"]):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
