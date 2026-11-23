#!/usr/bin/env python3
"""Run a new, separately sealed SEC panel with one answer-only repair turn."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import fintech_inference_publication_gate_v2 as gate
import preflight_fintech_inference_new_issuer_v1 as preflight
import run_fintech_inference_new_issuer_flash_v1 as v1
import run_fresh_sec_multiissuer_flash_v1 as common
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


PROTOCOL = HERE / "FINTECH-INFERENCE-GUARDED-PANEL-PROTOCOL-v2.md"
CAP_USD = 0.15
RESERVE_NEXT_USD = 0.03
RESERVE_REPAIR_USD = 0.01
SEED = 2246
REPEATS = 5


def guarded_prompt(case_id, thesis_id, alert_id):
    initial = v1.prompt(case_id, thesis_id, alert_id)
    if case_id == "AFRM-FISCAL-COST":
        instruction = ("At the end, add exactly one line "
                       "[CHECK] AFRM_QOQ_REVENUE_DELTA=<FY2025 Q1 revenue minus FY2024 Q4 revenue in USD_thousand>.")
    elif case_id == "SOFI-REVENUE-BRIDGE":
        instruction = ("At the end, add exactly one line "
                       "[CHECK] SOFI_Q3_GAAP_TO_ADJUSTED_REVENUE=<GAAP revenue - servicing adjustment "
                       "+ residual adjustment - debt-gain adjustment = adjusted revenue>, "
                       "using signed arithmetic values without units in that line.")
    else:
        instruction = ("At the end, add exactly one line "
                       "[CHECK] UPST_ADJUSTED_NET_LOSS_YOY=<WIDER or NARROWER>, "
                       "comparing Q3 2024 with Q3 2023 on the stated non-GAAP basis.")
    return initial + " " + instruction + " The check line is not a substitute for a complete source-grounded review."


def run_case(case, pilot):
    thesis = common.seed_case(pilot, case)
    event = v1.event_for(case)
    alert = common.base.ingest(pilot, case["symbol"], event)["results"][0]["alert"]
    publication = gate.run_with_one_repair(
        pilot, case, guarded_prompt(case["case_id"], thesis["id"], alert["id"]),
        CAP_USD, RESERVE_REPAIR_USD)
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    checks = {
        "policy_tools_only": bool(calls) and set(calls) <= common.ALLOWED_REVIEW_TOOLS,
        "one_review": len(reviews) == 1,
        "source_packet_exact": state["alerts"][0]["event"]["sources"] == event["sources"]
            and state["alerts"][0]["event"]["observed_metrics"] == event["observed_metrics"],
        "review_linked": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"],
        "guarded_review": len(reviews) == 1 and reviews[0]["rationale"].startswith(
            "Guarded review recorded") and len(reviews[0]["evidence"]) == 1
            and reviews[0]["evidence"][0].get("type") == "validated_accounting_lineage",
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "version_incremented": state["theses"][0]["thesis"]["version"] == 2,
        "no_trade": all("trade" not in (name or "") for name in calls),
        "publication_candidate": publication["publication_status"] == "candidate_for_manual_claim_review",
    }
    return state, checks, {"expected_event": event, "tool_calls": calls,
                           "publication_gate": publication}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    v1.configure_common()
    source_check = preflight.verify()
    if ("GUARDED-V2-FROZEN-BEFORE-MODEL: yes" not in PROTOCOL.read_text()
            or "LOCAL-RAW-FACT-AUDIT: complete" not in v1.SOURCE_AUDIT.read_text()):
        raise RuntimeError("v2 protocol/source audit lacks pre-run freeze markers")
    cases = json.loads(v1.CORPUS.read_text())["cases"]
    order = [(case["case_id"], repeat) for case in cases
             for repeat in range(1, REPEATS + 1)]
    random.Random(SEED).shuffle(order)
    if args.preflight_only:
        if bool(args.template_db) != bool(args.gateway_binary):
            parser.error("provide both --template-db and --gateway-binary")
        if args.template_db:
            common.dry_run_tool_setup(cases, args.template_db, args.gateway_binary)
        print(json.dumps({"preflight": "ok", "observations": len(order),
                          "source_preflight": source_check["preflight"],
                          "tool_setup": "ok" if args.template_db else "not_requested",
                          "run_order": order}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.output_dir.resolve().is_relative_to(ROOT.resolve()):
        parser.error("--output-dir must be within the repository")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    common.base.MODEL, common.base.PRICING, common.base.CAP_USD = (
        common.panel.MODEL, common.panel.PRICING, CAP_USD)
    paths = [Path(__file__), PROTOCOL, v1.CORPUS, v1.SOURCE_AUDIT,
             HERE / "FINTECH-INFERENCE-CLAIM-GATE-v1.json",
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "verify_fintech_inference_answer_v1.py",
             HERE / "fintech_inference_publication_gate_v2.py",
             HERE / "run_fintech_inference_new_issuer_flash_v1.py",
             HERE / "run_fresh_sec_multiissuer_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py",
             HERE / "workflow_runtime_audit_v2.py",
             Path(preflight.__file__), HERE / "audit_fintech_inference_sources_v1.py",
             PLUGIN_PATH, ROOT / "plugins/finance-tools/accounting_lineage.py",
             ROOT / "internal/policy/defaults.go"]
    paths += [HERE / case[period]["local_path"] for case in cases
              for period in ("baseline", "event")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=common.panel.MODEL, pricing=common.panel.PRICING,
                    run_order=order, random_seed=SEED, repeats_per_case=REPEATS,
                    policy="finance-review-only", source_preflight=source_check,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    reserve_repair_usd=RESERVE_REPAIR_USD,
                    max_answer_repairs=1,
                    old_v1_outputs_not_used_in_prompt=True)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    by_id = {case["case_id"]: case for case in cases}
    spent = 0.0
    try:
        with tempfile.TemporaryDirectory(prefix="fintech-guarded-v2-") as root:
            for case_id, repeat in order:
                if spent + RESERVE_NEXT_USD > CAP_USD:
                    print("STOP: conservative estimated-spend reserve reached", flush=True)
                    break
                observation_id = f"{case_id}-r{repeat}"
                pilot = common.panel.PanelPilot(observation_id, args.template_db,
                                                args.gateway_binary, root, False, spent)
                common.set_review_only(pilot.home)
                state, checks, extras, error = None, {}, {}, None
                process, log = None, None
                try:
                    process, log = common.base.start_gateway(pilot.home)
                    state, checks, extras = run_case(by_id[case_id], pilot)
                    trace_checks, trace_details = common.panel.trace_checks(pilot)
                    checks.update(trace_checks)
                    extras["trace"] = trace_details
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    try:
                        state = pilot.ledger_state()
                    except Exception:
                        pass
                finally:
                    directory = args.output_dir / observation_id
                    v1.save_turn_checkpoint(directory, pilot)
                    if process is not None:
                        try:
                            common.base.stop_gateway(process, log)
                        except Exception as exc:
                            error = (error + "; " if error else "") + f"cleanup {type(exc).__name__}: {exc}"
                    gateway_log = pilot.home / "gateway.log"
                    if gateway_log.is_file():
                        directory.mkdir(exist_ok=True)
                        shutil.copy2(gateway_log, directory / "gateway.log")
                runtime_audit = common.audit_turns(pilot.turns)
                spent += pilot.cost
                result = {
                    "observation_id": observation_id, "case_id": case_id,
                    "repeat": repeat, "workflow": "guarded_fintech_event_review_with_answer_gate",
                    "status": ("mechanical_pass" if error is None and checks
                               and all(checks.values()) and runtime_audit["clean_completion"]
                               else "needs_review"),
                    "error": error, "checks": checks, "runtime_audit": runtime_audit,
                    "state": state, "extras": extras, "turns": pilot.turns,
                    "estimated_cost_usd": pilot.cost,
                }
                directory = args.output_dir / observation_id
                directory.mkdir(exist_ok=True)
                (directory / "result.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                ledger = pilot.home / "finance-tools.db"
                if ledger.is_file():
                    shutil.copy2(ledger, directory / "finance-tools.db")
                print(json.dumps({"observation_id": observation_id,
                                  "status": result["status"],
                                  "publication_status": extras.get("publication_gate", {}).get("publication_status"),
                                  "error": error, "cost": pilot.cost,
                                  "cumulative_cost": spent}), flush=True)
                if (error or runtime_audit["request_errors"]
                        or runtime_audit["cost_uncertain_sequences"]
                        or runtime_audit["unpriced_sequences"]):
                    print("STOP: request error or uncertain pricing", flush=True)
                    break
    finally:
        v1.write_result_hashes(args.output_dir)
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
