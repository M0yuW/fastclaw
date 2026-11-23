#!/usr/bin/env python3
"""Run the frozen three-issuer, 15-observation FinTech SEC holdout panel."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import preflight_fresh_fintech_sec_panel_v1 as source_preflight
import run_fresh_sec_multiissuer_flash_v1 as common
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


CORPUS = HERE / "fresh_fintech_sec_panel_v1.json"
PROTOCOL = HERE / "FRESH-FINTECH-SEC-PANEL-PROTOCOL-v1.md"
CAP_USD = 0.10
RESERVE_NEXT_USD = 0.02
REPEATS = 5
SEED = 2243
FACT_LINE = {
    "quarterly_net_revenue": "revenue",
    "service_revenue": "revenue",
    "current_quarter_payments_volume_growth_yoy": "unknown",
    "service_revenue_basis_prior_quarter_payments_volume_growth_yoy": "unknown",
    "cross_border_ex_intra_europe_growth_yoy": "unknown",
    "total_payment_volume": "unknown",
    "total_payment_volume_growth_yoy": "unknown",
    "transaction_margin_dollars": "unknown",
    "gaap_operating_margin": "unknown",
    "adjusted_operating_margin": "unknown",
    "gaap_operating_expense_growth_yoy": "operating_expense",
    "adjusted_operating_expense_growth_yoy": "operating_expense",
    "litigation_provision": "operating_expense",
    "restructuring_charge": "operating_expense",
}
REVIEW_METRICS = {
    "FINTECH-V-SERVICE-LAG": [
        "quarterly_net_revenue", "service_revenue",
        "current_quarter_payments_volume_growth_yoy",
        "service_revenue_basis_prior_quarter_payments_volume_growth_yoy",
    ],
    "FINTECH-PYPL-MIX": [
        "total_payment_volume", "total_payment_volume_growth_yoy",
        "quarterly_net_revenue", "transaction_margin_dollars",
        "gaap_operating_margin",
    ],
    "FINTECH-MA-GAAP-ADJ": [
        "quarterly_net_revenue", "gaap_operating_margin",
        "adjusted_operating_margin", "gaap_operating_expense_growth_yoy",
        "adjusted_operating_expense_growth_yoy",
    ],
}


def event_for(case):
    item = case["event"]
    observed = {}
    for fact in item["facts"]:
        metric = fact["metric"]
        entry = {"value": str(fact["value"]), "unit": fact["unit"],
                 "fact_id": fact["id"],
                 "statement_line": fact.get("statement_line", FACT_LINE[metric])}
        if "source_explicit_targets" in fact:
            entry["source_explicit_targets"] = fact["source_explicit_targets"]
        observed[metric] = entry
    return {
        "external_id": case["case_id"] + "-sec-event-v1",
        "type": "earnings", "as_of": item["as_of"],
        "summary": (f"{case['symbol']} {item['period']} selected SEC exhibit packet: "
                    + common.fact_text(item["facts"])
                    + ". Compare with the supplied baseline; disclosed year-over-year "
                      "rates are not sequential growth calculations."),
        "sources": [common.source_ref(case, "event")],
        "observed_metrics": observed,
    }


def prompt(case_id, thesis_id, alert_id):
    return (
        common.base.review_prompt(case_id, thesis_id, alert_id)
        + " Compare adjacent fiscal-quarter levels when metric, unit and "
          "accounting basis match; keep disclosed year-over-year rates "
          "separate. Distinguish GAAP and adjusted measures, and timing of "
          "recognition where the packet states it. Identify one source-grounded "
          "research implication, its strongest counterpoint or unresolved "
          "input, and what evidence would change the assessment. Do not "
          "assume a direction or conviction in advance. For causal_claims, "
          "use a stored source-backed driver fact with a supported target; "
          "a metric is not its own cause. Qualitative directly_stated links "
          "need not have a quantified contribution. If no claim qualifies, "
          "send causal_claims=[]. Do not set next_review_at to a past date; "
          "omit it unless there is a genuine future operational review date. "
          "Read tool results and correct rejected inputs before finalizing."
    )


def configure_common():
    common.FACT_LINE = FACT_LINE
    common.REVIEW_METRICS = REVIEW_METRICS
    common.event_for = event_for
    common.guarded_prompt = prompt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    configure_common()
    preflight = source_preflight.verify()
    cases = json.loads(CORPUS.read_text())["cases"]
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
                          "source_preflight": preflight["preflight"],
                          "tool_setup": "ok" if args.template_db else "not_requested",
                          "run_order": order}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    common.base.MODEL, common.base.PRICING, common.base.CAP_USD = (
        common.panel.MODEL, common.panel.PRICING, CAP_USD)
    paths = [Path(__file__), PROTOCOL, CORPUS, Path(source_preflight.__file__),
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
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    by_id = {case["case_id"]: case for case in cases}
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fresh-fintech-sec-") as root:
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
                if process is not None:
                    common.base.stop_gateway(process, log)
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
