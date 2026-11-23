#!/usr/bin/env python3
"""Two source-only, guarded finance-review observations; no archived outputs sent."""

import argparse
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_intel_charge_bridge_retest_flash_v1 as intel
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


PROTOCOL = HERE / "GUARDED-SEC-REVIEW-PILOT-PROTOCOL-v1.md"
CAP_USD = 0.015
CASES = ("INTC", "NKE")
ALLOWED_REVIEW_TOOLS = {
    "finance-tools__thesis_get", "finance-tools__thesis_list",
    "finance-tools__alert_list", "finance-tools__thesis_match_event",
    "finance-tools__thesis_record_review", "finance-tools__alert_update",
}


def preflight():
    bridge, _ = intel.preflight()
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    for source_id in ("intel-2024-08-01-q2", "intel-2024-10-31-q3",
                      "nike-2024-06-27-fy2024", "nike-2024-12-19-q2-fy2025"):
        item = lock[source_id]
        if sha256(HERE / item["local_path"]) != item["sha256"]:
            raise ValueError(f"source-lock mismatch for {source_id}")
    before, _ = base.event_from_episode(
        "FSEC-NKE-01", ["NKE-Q4FY24-REV", "NKE-Q4FY24-GM", "NKE-Q4FY24-DIGITAL"])
    after, _ = base.event_from_episode(
        "FSEC-NKE-02", ["NKE-Q2FY25-REV", "NKE-Q2FY25-GM", "NKE-Q2FY25-DIGITAL"])
    if (before["observed_metrics"]["gross_margin"]["value"] != "44.7" or
            after["observed_metrics"]["gross_margin"]["value"] != "43.6" or
            after["observed_metrics"]["nike_brand_digital_yoy"]["value"] != "-21"):
        raise ValueError("Nike case differs from frozen episode facts")
    return bridge, lock


def classified_event(symbol, bridge):
    if symbol == "INTC":
        event = intel.enriched_event(bridge)
        lines = {
            "quarterly_revenue": "revenue",
            "gross_margin": "unknown",
            "restructuring_charges": "unknown",
            "impairment_and_accelerated_depreciation": "unknown",
            "manufacturing_asset_impairment_and_accelerated_depreciation": "cost_of_sales",
            "goodwill_and_intangible_impairment": "operating_expense",
            "deferred_tax_asset_valuation_allowance": "income_tax",
        }
        for name, metric in event["observed_metrics"].items():
            metric["statement_line"] = lines[name]
        return event
    event, _ = base.event_from_episode(
        "FSEC-NKE-02", ["NKE-Q2FY25-REV", "NKE-Q2FY25-GM", "NKE-Q2FY25-DIGITAL"])
    event["observed_metrics"]["quarterly_revenue"]["statement_line"] = "revenue"
    event["observed_metrics"]["gross_margin"]["statement_line"] = "unknown"
    event["observed_metrics"]["nike_brand_digital_yoy"]["statement_line"] = "revenue"
    for name, fact_id, line in (
        ("higher_discounts", "NKE-Q2FY25-DISCOUNTS", "contra_revenue"),
        ("adverse_channel_mix", "NKE-Q2FY25-CHANNEL-MIX", "revenue_mix"),
        ("lower_input_costs", "NKE-Q2FY25-INPUT-COSTS", "cost_of_sales"),
        ("lower_logistics_costs", "NKE-Q2FY25-LOGISTICS-COSTS", "cost_of_sales"),
    ):
        event["observed_metrics"][name] = {
            "value": "reported_qualitative", "unit": "qualitative",
            "fact_id": fact_id, "statement_line": line,
            "source_explicit_targets": ["gross_margin"],
        }
    event["summary"] += (
        " SEC source says gross margin declined 100 basis points to 43.6%, "
        "primarily due to higher discounts and channel-mix changes, partly "
        "offset by lower product input and warehousing/logistics costs."
    )
    return event


def set_review_only(home):
    with sqlite3.connect(home / "fastclaw.db") as db:
        row = db.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
        agent = json.loads(row[0])
        agent.update(policy="finance-review-only", maxToolIterations=10, maxTokens=3500)
        db.execute("UPDATE agents SET config=? WHERE id=?", (json.dumps(agent), AGENT_ID))


def prompt(symbol, thesis_id, alert_id):
    return (
        base.review_prompt("GUARDED-" + symbol, thesis_id, alert_id)
        + " This is a source-classified event. For thesis_record_review provide "
          "causal_claims as an array of objects with target_metric, strength "
          "('directly_stated', 'consistent_with', or 'unresolved'), and "
          "driver_fact_ids from the STORED alert. Distinguish financial-statement "
          "lines; use directly_stated only if source_explicit_targets includes "
          "that target. Do not assign a numerical contribution without a source "
          "reconciliation. If a driver is unsupported, leave attribution unresolved. "
          "The tool validates claims and replaces your draft rationale in the "
          "ledger; read its result before your final answer. Choose impact, "
          "decision and conviction yourself."
    )


def run_case(symbol, pilot, event):
    if symbol == "INTC":
        baseline, ids, required = "FSEC-INTC-02", ["INTC-Q2-REV", "INTC-Q2-GM", "INTC-Q2-OM"], ["quarterly_revenue", "gross_margin"]
    else:
        baseline, ids, required = "FSEC-NKE-01", ["NKE-Q4FY24-REV", "NKE-Q4FY24-GM", "NKE-Q4FY24-DIGITAL"], ["quarterly_revenue", "gross_margin", "nike_brand_digital_yoy"]
    thesis = base.seed_thesis(
        pilot, baseline, ids,
        "Compare the supplied periods and preserve support, risk and uncertainty. "
        "Do not infer adjacent-quarter growth unless periods are adjacent.",
        required)
    alert = base.ingest(pilot, symbol, event)["results"][0]["alert"]
    pilot.turn(prompt(symbol, thesis["id"], alert["id"]))
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    checks = {
        "policy_tools_only": bool(calls) and set(calls) <= ALLOWED_REVIEW_TOOLS,
        "one_review": len(reviews) == 1,
        "source_packet_exact": state["alerts"][0]["event"]["sources"] == event["sources"]
            and state["alerts"][0]["event"]["observed_metrics"] == event["observed_metrics"],
        "review_linked": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"],
        "guarded_review": len(reviews) == 1 and reviews[0]["rationale"].startswith("Guarded review recorded")
            and len(reviews[0]["evidence"]) == 1
            and reviews[0]["evidence"][0].get("type") == "validated_accounting_lineage",
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "version_incremented": state["theses"][0]["thesis"]["version"] == 2,
        "no_decision_hold": state["theses"][0]["thesis"]["actionability"] == "available",
    }
    return state, checks, {"tool_calls": calls, "expected_event": event}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    bridge, lock = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": len(CASES), "symbols": CASES}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    paths = [Path(__file__), PROTOCOL, HERE / "intel_charge_bridge_v1.json",
             HERE / "evidence.json", HERE / "source-lock.json",
             HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_intel_charge_bridge_retest_flash_v1.py",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_thesis_event_panel.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH,
             ROOT / "plugins/finance-tools/accounting_lineage.py",
             ROOT / "internal/policy/defaults.go"]
    paths += [HERE / lock[source_id]["local_path"] for source_id in (
        "intel-2024-08-01-q2", "intel-2024-10-31-q3",
        "nike-2024-06-27-fy2024", "nike-2024-12-19-q2-fy2025")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=list(CASES), policy="finance-review-only",
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    archived_model_outputs_in_prompt=False)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="guarded-sec-pilot-") as root:
        for symbol in CASES:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            pilot = panel.PanelPilot("guarded-" + symbol, args.template_db,
                                     args.gateway_binary, root, False, spent)
            set_review_only(pilot.home)
            event = classified_event(symbol, bridge)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                state, checks, extras = run_case(symbol, pilot, event)
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
            result = {"case_id": symbol, "workflow": "guarded_event_review",
                      "status": "mechanical_pass" if error is None and checks
                      and all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / symbol
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            ledger_db = pilot.home / "finance-tools.db"
            if ledger_db.is_file():
                shutil.copy2(ledger_db, directory / "finance-tools.db")
            print(json.dumps({"case_id": symbol, "status": result["status"],
                              "failed_checks": [key for key, value in checks.items() if not value],
                              "error": error, "cost": pilot.cost,
                              "cumulative_cost": spent}), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": len(CASES), "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
