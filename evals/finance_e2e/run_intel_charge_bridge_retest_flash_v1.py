#!/usr/bin/env python3
"""Five isolated Intel SEC event reviews with source charge composition supplied."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns


BRIDGE = HERE / "intel_charge_bridge_v1.json"
PROTOCOL = HERE / "INTEL-CHARGE-BRIDGE-RETEST-PROTOCOL-v1.md"
CAP_USD = 0.03
REPETITIONS = 5
ORIGINAL_FACTS = ["INTC-Q3-REV", "INTC-Q3-GM", "INTC-Q3-RESTRUCT", "INTC-Q3-IMPAIR"]


def preflight():
    bridge = json.loads(BRIDGE.read_text())
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    source = lock[bridge["source_id"]]
    if (source["url"] != bridge["source_url"] or
            source["sha256"] != bridge["source_sha256"] or
            sha256(HERE / source["local_path"]) != source["sha256"]):
        raise ValueError("SEC source URL or hash differs from frozen bridge")
    if (sum(int(item["value"]) for item in bridge["composition"]) != bridge["bundle_usd_million"] or
            bridge["bundle_usd_million"] != 15900 or
            bridge["separate_restructuring_usd_million"] != 2800 or
            {item["value"] for item in bridge["composition"]} != {"3100", "2900", "9900"}):
        raise ValueError("composition arithmetic or charge separation invalid")
    baseline, _ = base.event_from_episode(
        "FSEC-INTC-02", ["INTC-Q2-REV", "INTC-Q2-GM", "INTC-Q2-OM"])
    event, _ = base.event_from_episode("FSEC-INTC-03", ORIGINAL_FACTS)
    if (baseline["observed_metrics"]["gross_margin"]["value"] != "35.4" or
            event["observed_metrics"]["gross_margin"]["value"] != "15.0" or
            event["observed_metrics"]["impairment_and_accelerated_depreciation"]["value"] != "15900"):
        raise ValueError("baseline or event differs from frozen evidence")
    return bridge, source


def enriched_event(bridge):
    event, _ = base.event_from_episode("FSEC-INTC-03", ORIGINAL_FACTS)
    for fact in bridge["composition"]:
        event["observed_metrics"][fact["metric"]] = {
            "value": fact["value"], "unit": fact["unit"], "fact_id": fact["fact_id"]}
    event["summary"] += (
        " Source charge composition: USD 3.1 billion manufacturing-asset impairment "
        "and accelerated depreciation, substantially all recognized in cost of sales; "
        "USD 2.9 billion goodwill and acquired-intangible impairment; USD 9.9 billion "
        "US deferred-tax-asset valuation allowance. These three sum to the separately "
        "reported USD 15.9 billion bundle; USD 2.8 billion restructuring is additional."
    )
    return event


def execute(pilot, event):
    thesis = base.seed_thesis(
        pilot, "FSEC-INTC-02", ["INTC-Q2-REV", "INTC-Q2-GM", "INTC-Q2-OM"],
        "Compare the supplied periods and preserve any risks or uncertainty. "
        "Do not infer adjacent-quarter growth unless the periods are adjacent.",
        ["quarterly_revenue", "gross_margin"])
    alert = base.ingest(pilot, thesis["symbol"], event)["results"][0]["alert"]
    pilot.turn(base.review_prompt("H-INTC", thesis["id"], alert["id"])
               + " Copy material values and units accurately, distinguish growth from margin "
                 "change, and explain any evidence limitation.")
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    current = state["theses"][0]["thesis"]
    stored = state["alerts"][0]["event"]
    checks = {
        "one_review": len(reviews) == 1,
        "source_packet_exact": stored["sources"] == event["sources"]
            and stored["observed_metrics"] == event["observed_metrics"]
            and stored["summary"] == event["summary"],
        "review_linked": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"]
            and reviews[0]["event"]["sources"] == event["sources"],
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "version_incremented": current["version"] == 2,
        "missing_metric_policy": len(reviews) == 1 and not reviews[0]["missing_metrics"],
        "missing_metric_actionability": current["actionability"] == "available",
    }
    return state, checks, {"expected_source": event["sources"],
                            "expected_metrics": event["observed_metrics"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    bridge, source = preflight()
    event = enriched_event(bridge)
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "planned": REPETITIONS,
                          "source_sha256": bridge["source_sha256"]}))
        return
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("--template-db, --gateway-binary and --output-dir are required")
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    paths = [Path(__file__), BRIDGE, PROTOCOL, HERE / "evidence.json",
             HERE / "source-lock.json", HERE / "INSIGHT-QUALITY-JUDGE-RUBRIC-v1.md",
             HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_thesis_event_panel.py",
             HERE / "run_thesis_event_gateway.py", HERE / "workflow_runtime_audit_v2.py",
             PLUGIN_PATH, HERE / source["local_path"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING,
                    run_order=[f"H-INTC-BRIDGE-r{repeat}" for repeat in range(1, REPETITIONS + 1)],
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    single_treatment="SEC charge composition added to Intel event packet")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="intel-charge-bridge-") as root:
        for repeat in range(1, REPETITIONS + 1):
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            observation_id = f"H-INTC-BRIDGE-r{repeat}"
            pilot = panel.PanelPilot(observation_id, args.template_db,
                                     args.gateway_binary, root, False, spent)
            state, checks, extras, error = None, {}, {}, None
            process, log = None, None
            try:
                process, log = base.start_gateway(pilot.home)
                state, checks, extras = execute(pilot, event)
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
            result = {"observation_id": observation_id, "case_id": "H-INTC-BRIDGE",
                      "repetition": repeat, "workflow": "E", "synthetic_tool_fixture": False,
                      "status": "mechanical_pass" if error is None and checks
                      and all(checks.values()) and audit["clean_completion"] else "needs_review",
                      "error": error, "checks": checks, "runtime_audit": audit,
                      "state": state, "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            ledger_db = pilot.home / "finance-tools.db"
            if ledger_db.is_file():
                shutil.copy2(ledger_db, directory / "finance-tools.db")
            print(json.dumps({"observation_id": observation_id, "status": result["status"],
                              "error": error, "estimated_cost_usd": pilot.cost,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if error or audit["request_errors"] or audit["cost_uncertain_sequences"] or audit["unpriced_sequences"]:
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "planned": REPETITIONS, "estimated_cost_usd": spent}), flush=True)


if __name__ == "__main__":
    main()
