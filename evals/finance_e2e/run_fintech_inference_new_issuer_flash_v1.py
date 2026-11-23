#!/usr/bin/env python3
"""Run the prospective new-issuer SEC inference panel after source freeze."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import preflight_fintech_inference_new_issuer_v1 as source_preflight
import run_fresh_sec_multiissuer_flash_v1 as common
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


CORPUS = HERE / "fintech_inference_new_issuer_v1.json"
PROTOCOL = HERE / "FINTECH-INFERENCE-NEW-ISSUER-PROTOCOL-v1.md"
SOURCE_AUDIT = HERE / "FINTECH-INFERENCE-SOURCE-AUDIT-v1.md"
CAP_USD = 0.10
RESERVE_NEXT_USD = 0.02
REPEATS = 5
SEED = 2245
REVIEW_METRICS = {
    "AFRM-FISCAL-COST": [
        "gaap_total_revenue_net", "transaction_costs_non_gaap",
        "revenue_less_transaction_costs_non_gaap", "gaap_operating_income_loss",
        "adjusted_operating_income_non_gaap", "provision_for_credit_losses",
        "funding_costs",
    ],
    "SOFI-REVENUE-BRIDGE": [
        "gaap_total_net_revenue", "adjusted_net_revenue_non_gaap",
        "gaap_net_income_loss", "servicing_rights_valuation_adjustment",
        "residual_interests_valuation_adjustment",
        "gain_on_extinguishment_adjustment",
    ],
    "UPST-MIXED-BASIS": [
        "gaap_total_revenue", "gaap_operating_income_loss",
        "gaap_net_income_loss", "gain_on_debt_extinguishment",
        "adjusted_net_income_loss_non_gaap",
        "contribution_profit_non_gaap", "adjusted_ebitda_non_gaap",
        "gaap_operating_income_loss_prior_year_same_quarter",
        "adjusted_net_income_loss_prior_year_same_quarter_non_gaap",
    ],
}


def event_for(case):
    item = case["event"]
    observed = {}
    for fact in item["facts"]:
        observed[fact["metric"]] = {
            "value": str(fact["value"]), "unit": fact["unit"],
            "fact_id": fact["id"], "statement_line": fact["statement_line"],
        }
    return {
        "external_id": case["case_id"] + "-sec-event-v1",
        "type": "earnings", "as_of": item["as_of"],
        "summary": (f"{case['symbol']} {item['period']} selected SEC exhibit packet: "
                    + common.fact_text(item["facts"])
                    + ". Compare with the supplied historical baseline. "
                      "Keep sequential, year-over-year, GAAP and non-GAAP "
                      "comparisons on their stated bases."),
        "sources": [common.source_ref(case, "event")],
        "observed_metrics": observed,
    }


def prompt(case_id, thesis_id, alert_id):
    return (
        common.base.review_prompt(case_id, thesis_id, alert_id)
        + " Separate source facts, arithmetic and hypotheses; cite the fact IDs, "
          "periods, units and accounting bases for material claims. Identify "
          "one source-grounded research implication, its strongest counterpoint "
          "or unresolved input, and what evidence would change the assessment. "
          "Do not assume a decision, conviction, or that a positive change in one "
          "measure resolves contrary evidence in another. For causal_claims, "
          "use only a stored source-backed driver and supported target; omit "
          "unsupported causal claims. Do not set a past next_review_at date. "
          "Read and repair rejected tool inputs before finalizing."
    )


def configure_common():
    common.REVIEW_METRICS = REVIEW_METRICS
    common.event_for = event_for
    common.guarded_prompt = prompt


def write_result_hashes(output_dir):
    paths = [output_dir / "manifest.json", *sorted(output_dir.glob("*/result.json")),
             *sorted(output_dir.glob("*/turn_checkpoint.json")),
             *sorted(output_dir.glob("*/gateway.log"))]
    lines = [f"{sha256(path)}  {path.resolve().relative_to(ROOT.resolve())}"
             for path in paths]
    (output_dir / "RESULT-SHA256.txt").write_text("\n".join(lines) + "\n")


def save_turn_checkpoint(directory, pilot):
    """Persist priced model output before Gateway cleanup or later scoring."""
    if not pilot.turns:
        return
    directory.mkdir(exist_ok=True)
    (directory / "turn_checkpoint.json").write_text(json.dumps({
        "turns": pilot.turns,
        "estimated_cost_usd": pilot.cost,
    }, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    configure_common()
    source_check = source_preflight.verify()
    protocol_text = PROTOCOL.read_text(encoding="utf-8")
    audit_text = SOURCE_AUDIT.read_text(encoding="utf-8")
    if ("SOURCE-FROZEN-BEFORE-MODEL: yes" not in protocol_text
            or "LOCAL-RAW-FACT-AUDIT: complete" not in audit_text):
        raise RuntimeError("protocol/source audit lacks explicit pre-run freeze markers")
    cases = json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        assert len(event_for(case)["observed_metrics"]) == len(case["event"]["facts"])
        assert set(REVIEW_METRICS[case["case_id"]]) <= set(event_for(case)["observed_metrics"])
    order = [(case["case_id"], repeat) for case in cases
             for repeat in range(1, REPEATS + 1)]
    random.Random(SEED).shuffle(order)
    if args.preflight_only:
        if args.template_db or args.gateway_binary:
            if not all((args.template_db, args.gateway_binary)):
                parser.error("provide both --template-db and --gateway-binary")
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
    paths = [Path(__file__), PROTOCOL, SOURCE_AUDIT, CORPUS,
             HERE / "FINTECH-INFERENCE-CLAIM-GATE-v1.json",
             HERE / "prepare_fintech_inference_claim_review_v1.py",
             Path(source_preflight.__file__),
             HERE / "audit_fintech_inference_sources_v1.py",
             HERE / "validate_fintech_inference_packet_v1.py",
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
    manifest.update(model=common.panel.MODEL, pricing=common.panel.PRICING,
                    run_order=order, random_seed=SEED, repeats_per_case=REPEATS,
                    policy="finance-review-only",
                    source_preflight=source_check,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    by_id = {case["case_id"]: case for case in cases}
    spent = 0.0
    try:
        with tempfile.TemporaryDirectory(prefix="fintech-new-issuer-") as root:
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
                    state, checks, extras = common.run_case(by_id[case_id], pilot)
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
                    save_turn_checkpoint(directory, pilot)
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
                    "repeat": repeat, "workflow": "guarded_fintech_event_review",
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
                                  "failed_checks": [key for key, value in checks.items()
                                                    if not value],
                                  "error": error, "cost": pilot.cost,
                                  "cumulative_cost": spent}), flush=True)
                if (error or runtime_audit["request_errors"]
                        or runtime_audit["cost_uncertain_sequences"]
                        or runtime_audit["unpriced_sequences"]):
                    print("STOP: request error or uncertain pricing", flush=True)
                    break
    finally:
        write_result_hashes(args.output_dir)
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(order), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
