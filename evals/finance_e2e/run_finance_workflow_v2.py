#!/usr/bin/env python3
"""Repeat four differentiated finance workflows with frozen process/content checks."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256, source_ref
from test_thesis_event_integration import locked_episode

FIXTURES = HERE / "workflow_fixtures_v2"
CONFLICT = FIXTURES / "simulated_capex_statements.json"
CAP_USD = 0.10
RUN_ORDER = ["W02-r1", "W04-r1", "W01-r1", "W03-r1",
             "W03-r2", "W01-r2", "W04-r2", "W02-r2"]


def final_text(pilot):
    response = pilot.turns[-1]["response"] or {}
    choices = response.get("choices") or [{}]
    return choices[0].get("message", {}).get("content", "") or ""


def source_ref_for_conflict():
    if not CONFLICT.is_file():
        raise FileNotFoundError(CONFLICT)
    packet = json.loads(CONFLICT.read_text())
    if packet.get("fixture_id") != "synthetic-capex-conflict-v1":
        raise ValueError("wrong conflict fixture")
    if [s["id"] for s in packet["statements"]] != ["FICE-MEMO-A", "FICE-MEMO-B"]:
        raise ValueError("unexpected conflict sources")
    return packet, {"id": packet["fixture_id"],
                    "url": "local-fixture://synthetic-capex-conflict-v1",
                    "sha256": sha256(CONFLICT)}


def run_w01(pilot):
    thesis = base.seed_thesis(
        pilot, "FSEC-NVDA-01", ["NVDA-Q1-REV", "NVDA-Q1-GM", "NVDA-Q1-DC"],
        "Assess revenue and Data Center growth together with GAAP margin. "
        "A later sampled quarter is not necessarily adjacent to the preceding sample.",
        ["quarterly_revenue", "gross_margin", "data_center_revenue"])
    alert_ids = []
    for episode_id, facts in [
        ("FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-GM", "NVDA-Q2-DC"]),
        ("FSEC-NVDA-03", ["NVDA-Q4-REV", "NVDA-Q4-GM", "NVDA-Q4-DC"]),
    ]:
        event, _ = base.event_from_episode(episode_id, facts)
        ingested = base.ingest(pilot, "NVDA", event)
        alert = ingested["results"][0]["alert"]
        alert_ids.append(alert["id"])
        pilot.turn(base.review_prompt(pilot.case_id, thesis["id"], alert["id"])
                   + " Copy source numbers exactly; do not round them before computing changes. "
                     "Do not label nonadjacent sampled quarters as quarter-over-quarter.")
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    text = "\n".join(r["rationale"] for r in reviews) + "\n" + "\n".join(
        (t["response"] or {}).get("choices", [{}])[0].get("message", {}).get("content", "")
        for t in pilot.turns)
    checks = {
        "two_alerts": len(state["alerts"]) == 2,
        "two_reviews": len(reviews) == 2,
        "version_three": state["theses"][0]["thesis"]["version"] == 3,
        "linked_both": {r["alert_id"] for r in reviews} == set(alert_ids),
        "acknowledged_both": all(a["status"] == "acknowledged" for a in state["alerts"]),
        "baseline_exact": "26044" in text.replace(",", "") and "26040" not in text.replace(",", ""),
        "no_false_adjacent_label": "Q2 to Q4 QoQ" not in text and "Q2→Q4 QoQ" not in text,
    }
    return state, checks, {"alert_ids": alert_ids}


def run_w02(pilot):
    packet, source = source_ref_for_conflict()
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "FICE", "title": "Synthetic capacity-plan research thesis",
        "thesis": "Capacity expansion depends on a current, reconciled FY2025 capital expenditure plan. "
                  "When two management statements about the same plan disagree without an "
                  "explicit correction, preserve both claims and request clarification.",
        "status": "active", "conviction": 3,
        "catalysts": ["documented capacity investment"],
        "invalidations": ["unreconciled spending-plan change"],
        "required_event_metrics": ["capex_guidance_first", "capex_guidance_second"],
        "evidence": [source],
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
        "event_types": ["management_update"], "keywords": ["FICE"],
        "min_match_score": 1,
    }, pilot.tenant)
    a, b = packet["statements"]
    event = {
        "external_id": packet["fixture_id"], "type": "management_update",
        "as_of": b["issued_at"],
        "summary": "FICE simulated FY2025 capex evidence: " + a["text"] + " " + b["text"],
        "sources": [source],
        "observed_metrics": {
            "capex_guidance_first": {"value": "8000", "unit": "USD_million", "fact_id": a["id"]},
            "capex_guidance_second": {"value": "5000", "unit": "USD_million", "fact_id": b["id"]},
        },
    }
    alert = base.ingest(pilot, "FICE", event)["results"][0]["alert"]
    pilot.turn(
        "This is a synthetic research-state case, not a real security or market announcement. "
        "Read the stored FICE thesis and new alert. Compare both dated statements "
        "about the same FY2025 plan; do not assume the later statement automatically "
        "supersedes the earlier one without an explicit correction. Choose the review "
        "decision yourself. Record one linked, version-protected review with both source "
        "claims retained in its rationale, then acknowledge the alert. Do not trade. "
        f"Case {pilot.case_id}; thesis ID {thesis['id']}; alert ID {alert['id']}.")
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    rationale = reviews[0]["rationale"] if len(reviews) == 1 else ""
    actual = state["theses"][0]["thesis"]
    checks = {
        "one_review": len(reviews) == 1,
        "source_linked": len(reviews) == 1 and reviews[0]["event"]["sources"][0]["sha256"] == source["sha256"],
        "two_claims_retained": "8" in rationale and "5" in rationale,
        "conflict_deferred": len(reviews) == 1 and reviews[0]["decision"] == "needs_review",
        "state_unchanged": actual["status"] == "active" and actual["conviction"] == 3,
        "version_two": actual["version"] == 2,
        "alert_acknowledged": len(state["alerts"]) == 1 and state["alerts"][0]["status"] == "acknowledged",
    }
    return state, checks, {"synthetic_source": source}


def run_w03(pilot):
    pilot.turn(
        "This is a synthetic, non-investment research workflow using fixture tickers "
        "FICC and FICD. Call finance-tools__screen_stocks for both with "
        "require_complete=true. Read retained and rejected candidates. Create one "
        "preliminary thesis only for a retained candidate. In the persisted thesis text, "
        "include the exact P/E, free-cash-flow, and ROIC numeric values from the tool, "
        "the missingness boundary, and synthetic fixture provenance. Do not create a "
        "thesis for a rejected candidate, call live market tools, or trade. "
        f"Case {pilot.case_id}.")
    state = pilot.ledger_state()
    names = [name for turn in pilot.turns for name in turn["tool_calls"]]
    theses = [entry["thesis"] for entry in state["theses"]]
    text = theses[0]["thesis"] if len(theses) == 1 else ""
    checks = {
        "screen_called": "finance-tools__screen_stocks" in names,
        "one_complete_candidate_thesis": len(theses) == 1 and theses[0]["symbol"] == "FICC",
        "pe_persisted": "16.5" in text,
        "free_cash_flow_persisted": "310" in text,
        "roic_persisted": "0.13" in text or "13%" in text or "13 %" in text,
        "fixture_provenance_persisted": "synthetic" in text.lower() or "fixture" in text.lower(),
        "no_alerts": not state["alerts"],
    }
    return state, checks, {}


def run_w04(pilot):
    pilot.turn(
        "This is a synthetic portfolio-risk diagnostic, not a live account. "
        "Holdings are FICA 45%, FICB 30%, and FICC 25%; the single-holding "
        "concentration policy limit is 50%. Call finance-tools__portfolio_risk "
        "with view=concentration. State whether the measured portfolio breaches "
        "the limit, and propose only a reversible human-review step if warranted. "
        "Do not trade, alter holdings, or create ledger records. "
        f"Case {pilot.case_id}.")
    state = pilot.ledger_state()
    names = [name for turn in pilot.turns for name in turn["tool_calls"]]
    final = final_text(pilot).lower()
    checks = {
        "risk_tool_called": "finance-tools__portfolio_risk" in names,
        "no_ledger_mutation": not state["theses"] and not state["alerts"],
        "largest_weight_and_limit": "45" in final and "50" in final,
        "no_false_breach": "no breach" in final or "not breach" in final
                           or "within" in final or "below" in final,
        "no_trade_tool": all("trade" not in (name or "") for name in names),
    }
    return state, checks, {}


FUNCTIONS = {"W01": (run_w01, False), "W02": (run_w02, True),
             "W03": (run_w03, True), "W04": (run_w04, True)}


def preflight():
    if len(RUN_ORDER) != 8 or set(RUN_ORDER) != {
        f"W{number:02d}-r{repeat}" for number in range(1, 5) for repeat in (1, 2)
    }:
        raise ValueError("run order must include four workflows twice")
    for episode in ("FSEC-NVDA-01", "FSEC-NVDA-02", "FSEC-NVDA-03"):
        locked_episode(episode)
    source_ref_for_conflict()
    for filename in ("stock_data.py", "portfolio_analytics.py"):
        if not list(FIXTURES.rglob(filename)):
            raise FileNotFoundError(filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    preflight()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "test_thesis_event_integration.py", HERE / "evidence.json",
             HERE / "source-lock.json", PLUGIN_PATH,
             ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go",
             *FIXTURES.rglob("*.py"), CONFLICT]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest["gateway_binary_sha256"] = sha256(args.gateway_binary)
    manifest["gateway_template_db_sha256"] = sha256(args.template_db)
    manifest["estimated_spend_stop_usd"] = CAP_USD
    manifest["run_order"] = RUN_ORDER
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    base.FIXTURES = FIXTURES
    base.CAP_USD = CAP_USD
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-workflow-v2-") as temp_root:
        for run_id in RUN_ORDER:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            function, synthetic = FUNCTIONS[run_id[:3]]
            pilot = base.Pilot(run_id, args.template_db, args.gateway_binary,
                               temp_root, synthetic, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = function(pilot)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                base.stop_gateway(process, log)
            spent += pilot.cost
            result = {
                "run_id": run_id, "synthetic_tool_fixture": synthetic,
                "status": "mechanical_pass" if error is None and all(checks.values()) else "needs_review",
                "error": error, "checks": checks, "state": state, "extras": extras,
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
