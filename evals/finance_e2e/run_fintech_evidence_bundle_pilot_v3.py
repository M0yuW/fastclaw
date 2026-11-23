#!/usr/bin/env python3
"""Three known-case engineering checks of source-derived note assembly."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import financial_evidence_bundle_v1 as evidence
import preflight_fintech_inference_new_issuer_v1 as preflight
import run_fintech_inference_new_issuer_flash_v1 as v1
import run_fresh_sec_multiissuer_flash_v1 as common
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


PROTOCOL = HERE / "FINTECH-EVIDENCE-BUNDLE-PILOT-PROTOCOL-v3.md"
CAP_USD = 0.05
RESERVE_NEXT_USD = 0.015
ORDER = ["SOFI-REVENUE-BRIDGE", "AFRM-FISCAL-COST", "UPST-MIXED-BASIS"]
RECONCILIATION_SPECS = {
    "SOFI-REVENUE-BRIDGE": [{"id": "REC:SOFI_Q3_ADJUSTED_REVENUE",
                             "base_fact_id": "SOFI-Q3-GAAP-REV",
                             "signed_adjustment_fact_ids": ["SOFI-Q3-SERVICING",
                                                            "SOFI-Q3-RESIDUAL",
                                                            "SOFI-Q3-DEBTGAIN"],
                             "reported_fact_id": "SOFI-Q3-ADJ-REV"}],
}


def build_bundles(cases):
    return {case["case_id"]: evidence.build_bundle(
        case, RECONCILIATION_SPECS.get(case["case_id"], ())) for case in cases}


def make_prompt(bundles):
    def prompt(case_id, thesis_id, alert_id):
        allowed_ids = [row["id"] for row in
                       [*bundles[case_id]["comparisons"], *bundles[case_id]["reconciliations"]]]
        return (
            v1.prompt(case_id, thesis_id, alert_id)
            + " A source-checked deterministic calculator has already produced "
              "the following evidence bundle. Treat its arithmetic and signed "
              "adjustments as authoritative; do not recompute them or invent "
              "additional numeric claims. "
            + json.dumps(bundles[case_id], separators=(",", ":"), ensure_ascii=False)
            + " After the required finance-tool review and alert acknowledgement, "
              "return only one JSON object, without Markdown fences, with exactly "
              "these fields: implication, counterpoint, next_evidence (each a "
              "substantive qualitative sentence with no digits, percentages or "
              "currency amounts); comparison_ids (a nonempty array chosen from "
            + json.dumps(allowed_ids)
            + "); causal_status (observation_only or bounded_hypothesis; do not "
              "claim a source-explicit causal bridge from an accounting identity); "
              "decision (the exact decision you stored: maintain, upgrade, "
              "downgrade, needs_review, or invalidate). The host will render "
              "the verified numeric table separately. Do not trade."
        )
    return prompt


def assemble(pilot, bundle, state):
    raw = pilot.turns[-1]["response"]["choices"][0]["message"]["content"]
    payload = json.loads(raw)
    validation = evidence.validate_interpretation(payload, bundle)
    stored_decision = state["theses"][0]["reviews"][0]["decision"]
    if payload["decision"] != stored_decision:
        raise ValueError("model decision differs from stored review")
    return {"validation": validation, "interpretation": payload,
            "assembled_note": evidence.render_research_note(bundle, payload)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    source_check = preflight.verify()
    if "EVIDENCE-BUNDLE-V3-FROZEN-BEFORE-MODEL: yes" not in PROTOCOL.read_text():
        raise RuntimeError("v3 engineering protocol not frozen")
    cases = json.loads(v1.CORPUS.read_text())["cases"]
    by_id = {case["case_id"]: case for case in cases}
    if set(by_id) != set(ORDER):
        raise ValueError("unexpected engineering-pilot case set")
    bundles = build_bundles(cases)
    v1.configure_common()
    common.guarded_prompt = make_prompt(bundles)
    if args.preflight_only:
        if bool(args.template_db) != bool(args.gateway_binary):
            parser.error("provide both --template-db and --gateway-binary")
        if args.template_db:
            common.dry_run_tool_setup(cases, args.template_db, args.gateway_binary)
        print(json.dumps({"preflight": "ok", "cases": ORDER,
                          "source_preflight": source_check["preflight"],
                          "comparison_counts": {key: len(value["comparisons"])
                                                for key, value in bundles.items()},
                          "tool_setup": "ok" if args.template_db else "not_requested"}))
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
             HERE / "derive_financial_comparisons_v1.py",
             HERE / "financial_evidence_bundle_v1.py",
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
                    run_order=ORDER, source_preflight=source_check,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    retries=0, development_cases_only=True)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    try:
        with tempfile.TemporaryDirectory(prefix="fintech-bundle-v3-") as root:
            for case_id in ORDER:
                if spent + RESERVE_NEXT_USD > CAP_USD:
                    print("STOP: conservative estimated-spend reserve reached", flush=True)
                    break
                pilot = common.panel.PanelPilot(case_id + "-v3", args.template_db,
                                                args.gateway_binary, root, False, spent)
                common.set_review_only(pilot.home)
                state, checks, extras, error = None, {}, {}, None
                process, log = None, None
                try:
                    process, log = common.base.start_gateway(pilot.home)
                    state, checks, extras = common.run_case(by_id[case_id], pilot)
                    trace_checks, trace_details = common.panel.trace_checks(pilot)
                    checks.update(trace_checks)
                    extras["trace"] = trace_details
                    try:
                        extras["assembly"] = assemble(pilot, bundles[case_id], state)
                        checks["evidence_bundle_assembled"] = True
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        extras["assembly_error"] = f"{type(exc).__name__}: {exc}"
                        checks["evidence_bundle_assembled"] = False
                except Exception as exc:
                    error = f"{type(exc).__name__}: {exc}"
                    try:
                        state = pilot.ledger_state()
                    except Exception:
                        pass
                finally:
                    directory = args.output_dir / case_id
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
                result = {"case_id": case_id,
                          "workflow": "guarded_sec_review_with_host_numeric_bundle",
                          "status": ("mechanical_pass" if error is None and checks
                                     and all(checks.values()) and runtime_audit["clean_completion"]
                                     else "needs_review"),
                          "error": error, "checks": checks, "runtime_audit": runtime_audit,
                          "state": state, "extras": extras, "turns": pilot.turns,
                          "estimated_cost_usd": pilot.cost}
                directory = args.output_dir / case_id
                directory.mkdir(exist_ok=True)
                (directory / "result.json").write_text(
                    json.dumps(result, indent=2, ensure_ascii=False) + "\n")
                ledger = pilot.home / "finance-tools.db"
                if ledger.is_file():
                    shutil.copy2(ledger, directory / "finance-tools.db")
                print(json.dumps({"case_id": case_id, "status": result["status"],
                                  "assembly_error": extras.get("assembly_error"),
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
                      "planned": len(ORDER), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
