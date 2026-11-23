#!/usr/bin/env python3
"""Prospective 3-issuer x 5-repeat source-only guarded review panel."""

import argparse
import json
import random
import shutil
import tempfile
from pathlib import Path

import preflight_fresh_sec_panel_v1 as preflight_module
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_guarded_sec_review_pilot_flash_v1 import (
    ALLOWED_REVIEW_TOOLS, prompt as guarded_prompt, set_review_only,
)
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


CORPUS = HERE / "fresh_sec_panel_v1.json"
PROTOCOL = HERE / "FRESH-SEC-MULTIISSUER-PANEL-PROTOCOL-v1.md"
AUDIT = HERE / "FRESH-SEC-SOURCE-AUDIT-v1.md"
CAP_USD = 0.10
RESERVE_NEXT_USD = 0.02
RANDOM_SEED = 2241
REPEATS = 5
FACT_LINE = {
    "quarterly_revenue": "revenue",
    "diluted_eps_gaap": "unknown",
    "diluted_eps_excluding_one_time_tax_charge": "unknown",
    "tax_charge_driver": "income_tax",
    "microsoft_cloud_revenue": "revenue",
    "microsoft_cloud_revenue_growth_yoy": "revenue",
    "azure_and_other_cloud_services_growth_yoy": "revenue",
    "global_comp_sales_growth_yoy": "revenue",
    "global_comp_transactions_growth_yoy": "revenue",
    "global_comp_ticket_growth_yoy": "revenue",
    "gaap_operating_margin": "unknown",
}
REVIEW_METRICS = {
    "FRESH-AAPL-TAX": ["quarterly_revenue", "diluted_eps_gaap",
                       "diluted_eps_excluding_one_time_tax_charge"],
    "FRESH-MSFT-CLOUD": ["quarterly_revenue", "microsoft_cloud_revenue",
                         "microsoft_cloud_revenue_growth_yoy",
                         "azure_and_other_cloud_services_growth_yoy"],
    "FRESH-SBUX-TRAFFIC": ["global_comp_sales_growth_yoy",
                           "global_comp_transactions_growth_yoy",
                           "global_comp_ticket_growth_yoy", "gaap_operating_margin"],
}


def source_ref(case, period):
    item = case[period]
    return {"id": f"{case['case_id']}-{period}-sec-exhibit",
            "url": item["source_url"], "sha256": item["source_sha256"]}


def fact_text(facts):
    return "; ".join(f"{fact['id']}={fact['value']} {fact['unit']}"
                     for fact in facts)


def event_for(case):
    item = case["event"]
    observed = {}
    for fact in item["facts"]:
        metric = fact["metric"]
        entry = {"value": str(fact["value"]), "unit": fact["unit"],
                 "fact_id": fact["id"], "statement_line": FACT_LINE[metric]}
        if metric == "tax_charge_driver":
            entry["source_explicit_targets"] = ["diluted_eps_gaap"]
        observed[metric] = entry
    return {"external_id": case["case_id"] + "-sec-event-v1",
            "type": "earnings", "as_of": {
                "AAPL": "2024-10-31", "MSFT": "2025-01-29",
                "SBUX": "2024-10-30"}[case["symbol"]],
            "summary": (f"{case['symbol']} {item['period']} selected SEC exhibit packet: "
                        + fact_text(item["facts"])
                        + ". Compare with the supplied baseline; disclosed year-over-year "
                          "rates are not sequential growth calculations."),
            "sources": [source_ref(case, "event")],
            "observed_metrics": observed}


def seed_case(pilot, case):
    baseline = case["baseline"]
    thesis = base.must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": case["symbol"],
        "title": f"{case['symbol']} SEC event research thesis",
        "thesis": (f"{baseline['period']} baseline: " + fact_text(baseline["facts"])
                   + ". Track the stated business thesis and compare only the supplied "
                     "periods; keep GAAP/non-GAAP and comparison bases distinct."),
        "status": "active", "conviction": 3,
        "catalysts": ["business growth", "earnings quality"],
        "invalidations": ["material operating deterioration", "weakening demand"],
        "required_event_metrics": REVIEW_METRICS[case["case_id"]],
        "evidence": [source_ref(case, "baseline")],
    }, pilot.tenant)["thesis"]
    base.must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": case["symbol"], "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [case["symbol"]],
        "min_match_score": 1,
    }, pilot.tenant)
    return thesis


def run_case(case, pilot):
    thesis = seed_case(pilot, case)
    event = event_for(case)
    alert = base.ingest(pilot, case["symbol"], event)["results"][0]["alert"]
    pilot.turn(guarded_prompt(case["case_id"], thesis["id"], alert["id"]))
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    checks = {
        "policy_tools_only": bool(calls) and set(calls) <= ALLOWED_REVIEW_TOOLS,
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
    }
    return state, checks, {"expected_event": event, "tool_calls": calls}


def dry_run_tool_setup(cases, template_db, gateway_binary):
    """Exercise actual plugin seeding/ingest for every case, without Gateway/model."""
    with tempfile.TemporaryDirectory(prefix="fresh-sec-preflight-") as root:
        for case in cases:
            pilot = panel.PanelPilot(case["case_id"] + "-preflight", template_db,
                                     gateway_binary, root, False, 0.0)
            set_review_only(pilot.home)
            thesis = seed_case(pilot, case)
            event = event_for(case)
            alert = base.ingest(pilot, case["symbol"], event)["results"][0]["alert"]
            state = pilot.ledger_state()
            assert state["theses"][0]["thesis"]["id"] == thesis["id"]
            assert state["alerts"][0]["id"] == alert["id"]
            assert state["alerts"][0]["event"]["observed_metrics"] == event["observed_metrics"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    source_preflight = preflight_module.verify()
    cases = json.loads(CORPUS.read_text())["cases"]
    for case in cases:
        assert len(event_for(case)["observed_metrics"]) == len(case["event"]["facts"])
        assert set(REVIEW_METRICS[case["case_id"]]) <= set(event_for(case)["observed_metrics"])
    order = [(case["case_id"], repeat) for case in cases
             for repeat in range(1, REPEATS + 1)]
    random.Random(RANDOM_SEED).shuffle(order)
    if args.preflight_only:
        if args.template_db or args.gateway_binary:
            if not all((args.template_db, args.gateway_binary)):
                parser.error("provide both --template-db and --gateway-binary for tool dry run")
            dry_run_tool_setup(cases, args.template_db, args.gateway_binary)
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
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    paths = [Path(__file__), PROTOCOL, AUDIT, CORPUS,
             HERE / "preflight_fresh_sec_panel_v1.py",
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_guarded_sec_review_pilot_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py",
             HERE / "workflow_runtime_audit_v2.py",
             PLUGIN_PATH, ROOT / "plugins/finance-tools/accounting_lineage.py",
             ROOT / "internal/policy/defaults.go"]
    paths += [HERE / case[period]["local_path"] for case in cases
              for period in ("baseline", "event")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=order, random_seed=RANDOM_SEED,
                    repeats_per_case=REPEATS, policy="finance-review-only",
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    reserve_next_observation_usd=RESERVE_NEXT_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    cases_by_id = {case["case_id"]: case for case in cases}
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fresh-sec-panel-") as root:
        for case_id, repeat in order:
            if spent + RESERVE_NEXT_USD > CAP_USD:
                print("STOP: conservative estimated-spend reserve reached", flush=True)
                break
            observation_id = f"{case_id}-r{repeat}"
            pilot = panel.PanelPilot(observation_id, args.template_db,
                                     args.gateway_binary, root, False, spent)
            set_review_only(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                state, checks, extras = run_case(cases_by_id[case_id], pilot)
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
            runtime_audit = audit_turns(pilot.turns)
            spent += pilot.cost
            result = {
                "observation_id": observation_id, "case_id": case_id,
                "repeat": repeat, "workflow": "guarded_event_review",
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
