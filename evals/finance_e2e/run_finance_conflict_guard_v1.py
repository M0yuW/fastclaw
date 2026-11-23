#!/usr/bin/env python3
"""Isolated two-source conflict regression with a deterministic decision hold."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_conflict_sources as prior
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as v2
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256

CAP_USD = 0.03


def run_case(pilot):
    documents, refs = prior.source_packet()
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "FICE", "title": "Synthetic capacity-plan research thesis",
        "thesis": "Capacity expansion depends on a reconciled FY2025 capital expenditure plan. "
                  "Uncorrected disagreement between two sources is a review hold, not proof "
                  "that the original conclusion is false.",
        "status": "active", "conviction": 3,
        "catalysts": ["verified capacity investment"],
        "invalidations": ["verified final FY2025 capital expenditure plan below USD 7 billion "
                          "after source reconciliation"],
        "evidence": refs,
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
        "event_types": ["management_update"], "keywords": ["FICE"], "min_match_score": 1,
    }, pilot.tenant)
    a, b = documents
    event = {
        "external_id": "synthetic-capex-two-source-guard-v1",
        "type": "management_update", "as_of": b["issued_at"],
        "summary": "FICE simulated FY2025 capital expenditure evidence: "
                   + a["statement"] + " " + b["statement"],
        "sources": refs,
        "source_claims": [
            {"metric": "capex_plan", "period": "FY2025", "value": doc["capex_plan_usd_million"],
             "unit": "USD_million", "fact_id": doc["fact_id"],
             "source_sha256": ref["sha256"]}
            for doc, ref in zip(documents, refs)
        ],
    }
    alert = base.ingest(pilot, "FICE", event)["results"][0]["alert"]
    if len(alert["event"]["unresolved_conflicts"]) != 1:
        raise ValueError("trusted ingestion failed to derive the source conflict")
    pilot.turn(
        "This is a synthetic research-state case, not real market data. Read the stored "
        "FICE thesis and alert. Evaluate both separately hashed statements about the same "
        "FY2025 plan; a later date alone is not an explicit correction. Choose the review "
        "decision yourself. If a finance tool rejects a review due to an unresolved source "
        "conflict, follow its stated rule and retry. Record a linked version-protected review "
        "that retains both claims, then acknowledge the alert. Do not trade. "
        f"Case {pilot.case_id}; thesis ID {thesis['id']}; alert ID {alert['id']}.")
    state = pilot.ledger_state()
    actual = state["theses"][0]["thesis"]
    reviews = state["theses"][0]["reviews"]
    review = reviews[0] if len(reviews) == 1 else None
    checks = {
        "one_review": bool(review),
        "both_sources_linked": bool(review) and
            {s["sha256"] for s in review["event"]["sources"]} ==
            {s["sha256"] for s in refs},
        "conflict_audited": bool(review) and len(review["unresolved_conflicts"]) == 1,
        "needs_review": bool(review) and review["decision"] == "needs_review",
        "conclusion_unchanged": actual["status"] == "active" and actual["conviction"] == 3,
        "decision_blocked": actual["actionability"] == "blocked" and
            actual["decision_hold_alert_id"] == alert["id"],
        "alert_acknowledged": len(state["alerts"]) == 1 and
            state["alerts"][0]["status"] == "acknowledged",
    }
    return state, checks, refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    prior.source_packet()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or gateway binary")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_conflict_sources.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             *prior.SOURCE_FILES, PLUGIN_PATH,
             ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go"]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    base.FIXTURES = v2.FIXTURES
    base.CAP_USD = CAP_USD
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-conflict-guard-") as temp_root:
        for run_id in ("W02G-r1", "W02G-r2"):
            if spent >= CAP_USD:
                break
            pilot = base.Pilot(run_id, args.template_db, args.gateway_binary,
                               temp_root, True, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, refs, error = None, {}, [], None
            try:
                state, checks, refs = run_case(pilot)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                base.stop_gateway(process, log)
            spent += pilot.cost
            result = {
                "run_id": run_id,
                "status": "mechanical_pass" if error is None and all(checks.values()) else "needs_review",
                "error": error, "checks": checks, "sources": refs, "state": state,
                "turns": pilot.turns, "estimated_cost_usd": pilot.cost,
            }
            directory = args.output_dir / run_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"run_id": run_id, "status": result["status"],
                              "error": error, "checks": checks,
                              "estimated_cost_usd": pilot.cost}, ensure_ascii=False), flush=True)
            if error or any(not turn["priced_usage"] for turn in pilot.turns):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": spent}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
