#!/usr/bin/env python3
"""One isolated Flash screen-to-preliminary-thesis run on frozen SEC disclosures."""

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as workflow
from run_thesis_event_gateway import load_plugin, must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from workflow_runtime_audit_v2 import audit_turns

CASE = HERE / "sec_disclosure_screen_q3_2024_v1.json"
FIXTURES = HERE / "workflow_fixtures_sec_screen_v1"
SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
CAP_USD = 0.01


def preflight():
    case = json.loads(CASE.read_text())
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    episodes = {item["id"]: item for item in json.loads((HERE / "evidence.json").read_text())["episodes"]}
    expected = {
        "AMD": ("FSEC-AMD-02", {"AMD-Q3-REV": "6819", "AMD-Q3-GM": "50",
                                      "AMD-Q3-GAME": "462"}),
        "INTC": ("FSEC-INTC-03", {"INTC-Q3-REV": "13300", "INTC-Q3-GM": "15.0",
                                        "INTC-Q3-RESTRUCT": "2800"}),
    }
    if case["case_id"] != "SEC-DISCLOSURE-SCREEN-Q3-2024-v1" or not SCRIPT.is_file():
        raise ValueError("unexpected frozen case or missing adapter")
    for candidate in case["candidates"]:
        entry = lock[candidate["source_id"]]
        if (entry["url"] != candidate["source_url"] or
                entry["sha256"] != candidate["source_sha256"] or
                sha256(HERE / entry["local_path"]) != entry["sha256"]):
            raise ValueError("frozen SEC source mismatch")
        episode_id, values = expected[candidate["symbol"]]
        facts = {item["id"]: item["value"] for item in episodes[episode_id]["facts"]}
        if any(facts.get(key) != value for key, value in values.items()):
            raise ValueError("candidate source facts differ from independently frozen episode")
    with tempfile.TemporaryDirectory(prefix="sec-screen-preflight-") as folder:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(folder) / "finance.db"),
                           "finskillsPath": str(FIXTURES), "evaluationFixture": True})
        tenant = {"userId": "sec-screen-preflight", "agentId": "finance-coordinator",
                  "sessionId": "preflight"}
        data = must_call(plugin, "screen_stocks", {
            "market": "US", "symbols": ["AMD", "INTC"],
            "require_complete": False}, tenant)
        if ([item["symbol"] for item in data["results"]] != ["AMD"] or
                [item["symbol"] for item in data["rejected"]] != ["INTC"] or
                sorted(data["rejected"][0]["failed_criteria"]) !=
                ["gaap_gross_margin_below_threshold", "revenue_yoy_below_threshold"]):
            raise ValueError("disclosure-only screen did not reproduce frozen oracle")
    return case


def prompt(case):
    return (
        "Run a historical, disclosure-only candidate-research workflow, not a live "
        "investment recommendation. Call finance-tools__screen_stocks for US symbols "
        "AMD and INTC with require_complete=false. This case's frozen offline adapter "
        "uses ONLY Q3 2024 SEC-reported GAAP gross margin >= 40% and revenue YoY "
        ">= 0%; the generic seven-factor market-data completeness gate is not the "
        "criterion here. Inspect retained AND rejected sets, source URLs, hashes, "
        "reporting periods, units, and risk notes. Decide whether a retained "
        "candidate warrants one HISTORICAL PRELIMINARY research thesis; if so, "
        "call finance-tools__thesis_save once, include the SEC URL and full SHA-256 "
        "in evidence, copy the material reported values, and explain risks and "
        "the missing valuation/price/analyst dimensions. Do not save a thesis "
        "for a rejected candidate. Do not call live market-data tools or trade. "
        "This is a frozen 2024 replay as of " + case["freeze_as_of"] + "."
    )


def tool_screen_data(pilot):
    for turn in pilot.turns:
        for event in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []:
            if event.get("type") == "tool_result" and event.get("name") == "finance-tools__screen_stocks":
                raw = event.get("result") or event.get("content")
                if isinstance(raw, str):
                    raw = json.loads(raw)
                if isinstance(raw, dict):
                    return raw
    return None


def score(case, pilot, state):
    theses = [entry["thesis"] for entry in state["theses"]]
    record = theses[0] if len(theses) == 1 else {}
    body = (record.get("thesis") or "").lower()
    title = (record.get("title") or "").lower()
    evidence = json.dumps(record.get("evidence") or [], ensure_ascii=False).lower()
    source = next(item for item in case["candidates"] if item["symbol"] == "AMD")
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    payload = tool_screen_data(pilot)
    data = payload.get("data") if isinstance(payload, dict) and payload.get("ok") else {}
    return {
        "screen_tool_called": "finance-tools__screen_stocks" in calls,
        "frozen_screen_results": bool(data) and
            [item.get("symbol") for item in data.get("results", [])] == ["AMD"] and
            [item.get("symbol") for item in data.get("rejected", [])] == ["INTC"] and
            data.get("synthetic") is False and data.get("offline_frozen_adapter") is True,
        "only_retained_candidate_saved": len(theses) == 1 and record.get("symbol") == "AMD",
        "historical_preliminary_label": "historical" in title and "preliminary" in title,
        "source_url_and_hash_in_evidence": source["source_url"].lower() in evidence and
            source["source_sha256"].lower() in evidence,
        "reported_values_and_risk": all(term in body for term in
            ("q3 2024", "6819", "18%", "50%", "462", "69%")),
        "not_live_or_valuation_claim": any(term in body for term in
            ("not live", "historical", "frozen")) and
            any(term in body for term in ("valuation", "price", "p/e")),
        "no_trade_or_extra_records": not state["alerts"] and
            all("trade" not in (name or "") for name in calls),
    }, {"screen_tool_payload": payload, "tool_calls": calls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    case = preflight()
    if args.preflight_only:
        print(json.dumps({"preflight": "ok", "case_id": case["case_id"]}))
        return
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = workflow.FIXTURES = FIXTURES
    paths = [Path(__file__), CASE, SCRIPT, HERE / "evidence.json",
             HERE / "source-lock.json", HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "workflow_runtime_audit_v2.py", PLUGIN_PATH]
    lock = {item["id"]: item for item in json.loads((HERE / "source-lock.json").read_text())["entries"]}
    paths += [HERE / lock[item["source_id"]]["local_path"] for item in case["candidates"]]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(case_id=case["case_id"], model=panel.MODEL, pricing=panel.PRICING,
                    estimated_spend_stop_usd=CAP_USD,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    source_boundary="frozen SEC original filings; offline adapter, no live prices",
                    sampling="one isolated exploratory observation")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="sec-disclosure-screen-") as folder:
        pilot = panel.PanelPilot("SEC-DISCLOSURE-SCREEN-Q3-2024", args.template_db,
                                 args.gateway_binary, folder, True, 0.0)
        process, log = None, None
        state, checks, extras, error = None, {}, {}, None
        try:
            process, log = base.start_gateway(pilot.home)
            pilot.turn(prompt(case))
            state = pilot.ledger_state()
            checks, extras = score(case, pilot, state)
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
        result = {"case_id": case["case_id"], "status": "mechanical_pass"
                  if error is None and checks and all(checks.values()) and
                  audit["clean_completion"] else "needs_review",
                  "error": error, "checks": checks, "runtime_audit": audit,
                  "state": state, "extras": extras, "turns": pilot.turns,
                  "estimated_cost_usd": pilot.cost}
        (args.output_dir / "result.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        shutil.copy2(pilot.home / "finance-tools.db", args.output_dir / "finance-tools.db")
        print(json.dumps({"status": result["status"], "error": error,
                          "failed_checks": [key for key, value in checks.items() if not value],
                          "estimated_cost_usd": pilot.cost,
                          "runtime_clean": audit["clean_completion"]},
                         ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
