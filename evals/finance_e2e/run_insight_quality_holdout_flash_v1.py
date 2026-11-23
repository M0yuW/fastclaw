#!/usr/bin/env python3
"""Run the four pre-frozen, source-locked event-to-thesis cases five times each."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_16_flash_v1 as cases
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CAP_USD = 0.12
REPETITIONS = 5
MODEL = panel.MODEL
CASES = {
    "H-AMD": ("FSEC-AMD-01", ["AMD-Q2-REV", "AMD-Q2-GM", "AMD-Q2-GAME"],
              "FSEC-AMD-02", ["AMD-Q3-REV", "AMD-Q3-GM", "AMD-Q3-GAME"],
              ["quarterly_revenue", "gross_margin", "gaming_revenue"]),
    "H-INTC": ("FSEC-INTC-02", ["INTC-Q2-REV", "INTC-Q2-GM", "INTC-Q2-OM"],
               "FSEC-INTC-03", ["INTC-Q3-REV", "INTC-Q3-GM", "INTC-Q3-RESTRUCT", "INTC-Q3-IMPAIR"],
               ["quarterly_revenue", "gross_margin"]),
    "H-NVDA": ("FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-GM", "NVDA-Q2-DC"],
               "FSEC-NVDA-03", ["NVDA-Q4-REV", "NVDA-Q4-GM", "NVDA-Q4-DC"],
               ["quarterly_revenue", "gross_margin", "data_center_revenue"]),
    "H-NKE": ("FSEC-NKE-01", ["NKE-Q4FY24-REV", "NKE-Q4FY24-GM", "NKE-Q4FY24-DIGITAL"],
              "FSEC-NKE-02", ["NKE-Q2FY25-REV", "NKE-Q2FY25-GM", "NKE-Q2FY25-DIGITAL"],
              ["quarterly_revenue", "gross_margin", "nike_brand_digital_yoy"]),
}
RUN_ORDER = [(case_id, repeat) for repeat in range(1, REPETITIONS + 1)
             for case_id in CASES]


def preflight():
    lock = json.loads((HERE / "source-lock.json").read_text())
    evidence = json.loads((HERE / "evidence.json").read_text())
    entries = {entry["id"]: entry for entry in lock["entries"]}
    episodes = {episode["id"]: episode for episode in evidence["episodes"]}
    checked_sources = set()
    for case_id, (before, before_facts, after, after_facts, required) in CASES.items():
        for episode_id, fact_ids in ((before, before_facts), (after, after_facts)):
            episode = episodes[episode_id]
            available = {fact["id"] for fact in episode["facts"]}
            if not set(fact_ids) <= available:
                raise ValueError(f"{case_id}: evidence IDs absent from {episode_id}")
            base.event_from_episode(episode_id, fact_ids)
            source_id = episode["source_id"]
            source = entries[source_id]
            local = HERE / source["local_path"]
            if hashlib.sha256(local.read_bytes()).hexdigest() != source["sha256"]:
                raise ValueError(f"{case_id}: source checksum mismatch: {source_id}")
            checked_sources.add(source_id)
        current_metrics = {fact["metric"] for fact in episodes[after]["facts"]
                           if fact["id"] in after_facts}
        if not set(required) <= current_metrics:
            raise ValueError(f"{case_id}: current event misses required metrics")
    return {"cases": list(CASES), "observations_planned": len(RUN_ORDER),
            "source_files_verified": len(checked_sources)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    checked = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", **checked}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required for a run")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = MODEL, panel.PRICING, CAP_USD
    paths = [Path(__file__), HERE / "INSIGHT-QUALITY-PROSPECTIVE-PROTOCOL-v1.md",
             HERE / "INSIGHT-QUALITY-STARTUP-GATE-RETEST-v1.md",
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md", HERE / "evidence.json",
             HERE / "source-lock.json", HERE / "run_finance_workflow_16_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_thesis_event_panel.py",
             HERE / "run_thesis_event_gateway.py", HERE / "workflow_runtime_audit_v2.py",
             PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=MODEL, pricing=panel.PRICING,
                    run_order=[f"{case_id}-r{repeat}" for case_id, repeat in RUN_ORDER],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    source_files_verified=checked["source_files_verified"],
                    source_boundary="SEC locked cache; historical research replay")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    cases.EVENTS.update(CASES)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-insight-holdout-") as temp_root:
        for case_id, repeat in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"{case_id}-r{repeat}"
            pilot = panel.PanelPilot(observation_id, args.template_db,
                                     args.gateway_binary, temp_root, False, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = cases.run_event(case_id, pilot)
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
                      "repetition": repeat, "workflow": "E",
                      "synthetic_tool_fixture": False,
                      "status": "mechanical_pass" if error is None and checks
                      and all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id, "status": result["status"],
                              "error": error, "estimated_cost_usd": pilot.cost,
                              "cumulative_estimated_cost_usd": spent}, ensure_ascii=False), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(RUN_ORDER), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
