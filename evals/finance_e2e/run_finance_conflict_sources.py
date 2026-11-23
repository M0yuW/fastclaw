#!/usr/bin/env python3
"""Two independent-hash synthetic source-conflict workflow repetitions."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as v2
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256

SOURCE_FILES = [v2.FIXTURES / "conflict_source_a.json",
                v2.FIXTURES / "conflict_source_b.json"]
CAP_USD = 0.03


def source_packet():
    documents = [json.loads(path.read_text()) for path in SOURCE_FILES]
    if [doc["fact_id"] for doc in documents] != ["FICE-MEMO-A", "FICE-MEMO-B"]:
        raise ValueError("unexpected conflict facts")
    if [doc["capex_plan_usd_million"] for doc in documents] != [8000, 5000]:
        raise ValueError("unexpected conflict values")
    refs = [{"id": doc["fixture_id"],
             "url": f"local-fixture://{doc['fixture_id']}",
             "sha256": sha256(path)}
            for path, doc in zip(SOURCE_FILES, documents)]
    if refs[0]["sha256"] == refs[1]["sha256"]:
        raise ValueError("source artifacts must have distinct hashes")
    return documents, refs


def run_case(pilot):
    documents, refs = source_packet()
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "FICE", "title": "Synthetic capacity-plan research thesis",
        "thesis": "Capacity expansion depends on a reconciled FY2025 capital expenditure plan. "
                  "When separate management statements about the same plan disagree without "
                  "an explicit correction, preserve both claims and request clarification.",
        "status": "active", "conviction": 3,
        "catalysts": ["documented capacity investment"],
        "invalidations": ["unreconciled spending-plan change"],
        "required_event_metrics": ["capex_guidance_first", "capex_guidance_second"],
        "evidence": refs,
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
        "event_types": ["management_update"], "keywords": ["FICE"],
        "min_match_score": 1,
    }, pilot.tenant)
    a, b = documents
    event = {
        "external_id": "synthetic-capex-two-source-event-v1",
        "type": "management_update", "as_of": b["issued_at"],
        "summary": "FICE simulated FY2025 capital expenditure evidence: "
                   + a["statement"] + " " + b["statement"],
        "sources": refs,
        "observed_metrics": {
            "capex_guidance_first": {
                "value": str(a["capex_plan_usd_million"]),
                "unit": "USD_million", "fact_id": a["fact_id"]},
            "capex_guidance_second": {
                "value": str(b["capex_plan_usd_million"]),
                "unit": "USD_million", "fact_id": b["fact_id"]},
        },
    }
    alert = base.ingest(pilot, "FICE", event)["results"][0]["alert"]
    pilot.turn(
        "This is a synthetic research-state case, not real market data. Read the stored "
        "FICE thesis and alert. Compare the two separately hashed, dated statements "
        "about the same FY2025 plan. Do not presume the later statement supersedes the "
        "earlier one without an explicit correction. Choose the decision yourself; "
        "record a linked version-protected review that retains both source claims and "
        "then acknowledge the alert. Do not trade. "
        f"Case {pilot.case_id}; thesis ID {thesis['id']}; alert ID {alert['id']}.")
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    review = reviews[0] if len(reviews) == 1 else None
    rationale = review["rationale"] if review else ""
    actual = state["theses"][0]["thesis"]
    checks = {
        "one_review": len(reviews) == 1,
        "both_independent_sources_linked": bool(review) and
            {s["sha256"] for s in review["event"]["sources"]} ==
            {s["sha256"] for s in refs},
        "two_claims_retained": "8" in rationale and "5" in rationale,
        "conflict_deferred": bool(review) and review["decision"] == "needs_review",
        "state_unchanged": actual["status"] == "active" and actual["conviction"] == 3,
        "version_two": actual["version"] == 2,
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
    source_packet()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_workflow_pilot.py",
             HERE / "run_finance_workflow_v2.py", *SOURCE_FILES,
             PLUGIN_PATH, ROOT / "internal/policy/defaults.go",
             ROOT / "internal/policy/engine.go"]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest["gateway_binary_sha256"] = sha256(args.gateway_binary)
    manifest["gateway_template_db_sha256"] = sha256(args.template_db)
    manifest["estimated_spend_stop_usd"] = CAP_USD
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    base.FIXTURES = v2.FIXTURES
    base.CAP_USD = CAP_USD
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-conflict-sources-") as temp_root:
        for run_id in ("W02S-r1", "W02S-r2"):
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
                "run_id": run_id, "status": "mechanical_pass" if error is None and
                all(checks.values()) else "needs_review", "error": error,
                "checks": checks, "sources": refs, "state": state,
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
