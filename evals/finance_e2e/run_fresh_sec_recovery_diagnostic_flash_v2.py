#!/usr/bin/env python3
"""Post-hoc six-observation recovery diagnostic; never a replacement for v1."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import run_fresh_sec_multiissuer_flash_v1 as v1
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


PROTOCOL = HERE / "FRESH-SEC-RECOVERY-DIAGNOSTIC-PROTOCOL-v2.md"
CAP_USD = 0.04
RESERVE_NEXT_USD = 0.01
REPEATS = 2
SEED = 2242


def comparison_and_causality_prompt(case_id, thesis_id, alert_id):
    return (
        v1.base.review_prompt(case_id, thesis_id, alert_id)
        + " Compare adjacent fiscal-quarter levels directly when the metric, "
          "unit, and accounting basis match; you may calculate their absolute "
          "or percent change. A separately disclosed year-over-year rate is "
          "not itself a quarter-over-quarter growth rate, but that does not "
          "make the adjacent-quarter levels incomparable. Do not conflate "
          "GAAP and adjusted values. A stored statement_line of unknown "
          "limits causal accounting classification; it does not negate a "
          "metric explicitly labeled GAAP. For causal_claims, use only a "
          "genuine source-backed driver fact targeting a supported accounting "
          "measure; a metric cannot be its own cause. If the selected packet "
          "has no supportable causal driver, submit causal_claims=[] and "
          "discuss uncertainty in the final answer. Read tool results, recover "
          "from a rejected claim, and choose the research decision yourself."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    source_preflight = v1.preflight_module.verify()
    cases = json.loads(v1.CORPUS.read_text())["cases"]
    order = [(case["case_id"], repeat) for case in cases
             for repeat in range(1, REPEATS + 1)]
    random.Random(SEED).shuffle(order)
    if args.preflight_only:
        if args.template_db or args.gateway_binary:
            if not all((args.template_db, args.gateway_binary)):
                parser.error("provide both --template-db and --gateway-binary")
            v1.dry_run_tool_setup(cases, args.template_db, args.gateway_binary)
        print(json.dumps({"preflight": "ok", "observations": len(order),
                          "source_preflight": source_preflight["preflight"],
                          "tool_setup": "ok" if args.template_db else "not_requested",
                          "run_order": order}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    v1.base.MODEL, v1.base.PRICING, v1.base.CAP_USD = (
        v1.panel.MODEL, v1.panel.PRICING, CAP_USD)
    v1.guarded_prompt = comparison_and_causality_prompt
    paths = [Path(__file__), PROTOCOL, v1.CORPUS,
             HERE / "FRESH-SEC-SOURCE-AUDIT-v1.md",
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_fresh_sec_multiissuer_flash_v1.py",
             HERE / "run_guarded_sec_review_pilot_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH,
             ROOT / "plugins/finance-tools/accounting_lineage.py",
             ROOT / "internal/policy/defaults.go"]
    paths += [HERE / case[period]["local_path"] for case in cases
              for period in ("baseline", "event")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=v1.panel.MODEL, pricing=v1.panel.PRICING,
                    run_order=order, random_seed=SEED, repeats_per_case=REPEATS,
                    policy="finance-review-only", diagnostic_not_holdout=True,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    by_id = {case["case_id"]: case for case in cases}
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fresh-sec-recovery-") as root:
        for case_id, repeat in order:
            if spent + RESERVE_NEXT_USD > CAP_USD:
                print("STOP: conservative estimated-spend reserve reached", flush=True)
                break
            observation_id = f"{case_id}-r{repeat}"
            pilot = v1.panel.PanelPilot(observation_id, args.template_db,
                                        args.gateway_binary, root, False, spent)
            v1.set_review_only(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = v1.base.start_gateway(pilot.home)
                state, checks, extras = v1.run_case(by_id[case_id], pilot)
                trace_checks, trace_details = v1.panel.trace_checks(pilot)
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
                    v1.base.stop_gateway(process, log)
            runtime_audit = v1.audit_turns(pilot.turns)
            spent += pilot.cost
            result = {
                "observation_id": observation_id, "case_id": case_id,
                "repeat": repeat, "workflow": "guarded_event_review_recovery_diagnostic",
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
