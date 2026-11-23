#!/usr/bin/env python3
"""One-shot exploratory panel: 16 distinct finance cases, Flash only.

E cases use locked SEC packets. C/S/P cases are explicitly synthetic. Each
case has a fresh Gateway home, session and finance ledger. This is not a
population reliability estimate or a model-quality benchmark.
"""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_finance_workflow_v2 as previous
from run_thesis_event_gateway import load_plugin, must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from test_thesis_event_integration import locked_episode

CAP_USD = 0.12
CASES = ["E1", "C1", "S1", "P1", "P2", "S2", "C2", "E2",
         "E3", "C3", "S3", "P3", "P4", "S4", "C4", "E4"]

EVENTS = {
    "E1": ("FSEC-AMD-02", ["AMD-Q3-REV", "AMD-Q3-GM", "AMD-Q3-GAME"],
           "FSEC-AMD-03", ["AMD-Q4-REV", "AMD-Q4-GM", "AMD-Q4-GAME"],
           ["quarterly_revenue", "gross_margin", "gaming_revenue"]),
    "E2": ("FSEC-NVDA-01", ["NVDA-Q1-REV", "NVDA-Q1-GM", "NVDA-Q1-DC"],
           "FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-GM", "NVDA-Q2-DC"],
           ["quarterly_revenue", "gross_margin", "data_center_revenue"]),
    "E3": ("FSEC-NKE-01", ["NKE-Q4FY24-REV", "NKE-Q4FY24-GM", "NKE-Q4FY24-DIGITAL"],
           "FSEC-NKE-03", ["NKE-Q4FY25-REV", "NKE-Q4FY25-GM", "NKE-Q4FY25-DIGITAL"],
           ["quarterly_revenue", "gross_margin", "nike_brand_digital_yoy"]),
    "E4": ("FSEC-NVDA-01", ["NVDA-Q1-REV", "NVDA-Q1-GM", "NVDA-Q1-DC"],
           "FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-DC"],
           ["quarterly_revenue", "gross_margin", "data_center_revenue"]),
}

SCREEN = {
    "S1": ("FICC and FICD", ""),
    "S2": ("FICB and FICD", ""),
    "S3": ("FICA", "the screen reports free cash flow of 420, while a separate "
           "synthetic analyst note reports 260 for the same period without a reconciliation"),
    "S4": ("FICA and FICC", "only candidates with P/E below 10 and ROIC at least 20% "
           "qualify for a preliminary thesis"),
}

PORTFOLIO = {
    "P1": ("FICA 45%, FICB 30%, FICC 25%", {"FICA": 45, "FICB": 30, "FICC": 25}, 45.0, False),
    "P2": ("FICA 50%, FICB 30%, FICC 20%", {"FICA": 50, "FICB": 30, "FICC": 20}, 50.0, False),
    "P3": ("FICA 65%, FICB 20%, FICC 15%", {"FICA": 65, "FICB": 20, "FICC": 15}, 65.0, True),
    "P4": ("FICA 45%, FICB 30%, and an unreported third holding", None, None, None),
}


def review_text(state):
    return state["theses"][0]["reviews"][0]["rationale"] if state["theses"] and state["theses"][0]["reviews"] else ""


def final_text(pilot):
    return previous.final_text(pilot)


def normalized_numbers(text):
    return text.replace(",", "").replace(" ", "")


def run_event(case_id, pilot):
    baseline, base_facts, current, current_facts, required = EVENTS[case_id]
    thesis = base.seed_thesis(
        pilot, baseline, base_facts,
        "Compare the supplied periods and preserve any risks or uncertainty. "
        "Do not infer adjacent-quarter growth unless the periods are adjacent.", required)
    event, _ = base.event_from_episode(current, current_facts)
    alert = base.ingest(pilot, thesis["symbol"], event)["results"][0]["alert"]
    pilot.turn(base.review_prompt(case_id, thesis["id"], alert["id"])
               + " Copy material values and units accurately, distinguish growth from margin "
                 "change, and explain any evidence limitation.")
    state = pilot.ledger_state()
    stored = state["alerts"][0]["event"]
    reviews = state["theses"][0]["reviews"]
    current_thesis = state["theses"][0]["thesis"]
    missing = sorted(set(required) - set(event["observed_metrics"]))
    if missing:
        missing_policy = (len(reviews) == 1 and reviews[0]["decision"] == "needs_review"
                          and reviews[0]["missing_metrics"] == missing
                          and current_thesis["conviction"] == 3
                          and current_thesis["status"] == "active")
    else:
        missing_policy = len(reviews) == 1 and not reviews[0]["missing_metrics"]
    checks = {
        "one_review": len(reviews) == 1,
        "source_packet_exact": stored["sources"] == event["sources"]
                               and stored["observed_metrics"] == event["observed_metrics"],
        "review_linked": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"]
                         and reviews[0]["event"]["sources"] == event["sources"],
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "version_incremented": current_thesis["version"] == (3 if missing else 2),
        "missing_metric_policy": missing_policy,
        "missing_metric_actionability": (
            current_thesis["actionability"] == "blocked"
            if missing else current_thesis["actionability"] == "available"
        ),
    }
    return state, checks, {"expected_source": event["sources"],
                           "expected_metrics": event["observed_metrics"],
                           "missing_metrics": missing}


def source_record(case_id, suffix, text):
    raw = text.encode()
    return {"id": f"{case_id}-{suffix}",
            "url": f"local-fixture://finance-16/{case_id}/{suffix}",
            "sha256": hashlib.sha256(raw).hexdigest(), "text": text}


def source_claim(source, metric, value, fact_id):
    return {"metric": metric, "period": "FY2025", "value": value,
            "unit": "USD_million", "fact_id": fact_id,
            "source_sha256": source["sha256"]}


def conflict_event(case_id):
    if case_id == "C1":
        docs = [source_record(case_id, "A", "FICE FY2025 capex plan: USD 8,000 million."),
                source_record(case_id, "B", "FICE FY2025 capex plan confirmed: USD 8,000 million.")]
        claims = [source_claim(docs[0], "capex_plan", 8000, "C1-A"),
                  source_claim(docs[1], "capex_plan", 8000, "C1-B")]
        observed = {"capex_plan": {"value": "8000", "unit": "USD_million", "fact_id": "C1-B"}}
        required = ["capex_plan"]
    elif case_id == "C2":
        docs = [source_record(case_id, "A", "FICE FY2025 capex plan: USD 8,000 million."),
                source_record(case_id, "B", "FICE FY2025 capex plan: USD 5,000 million; no correction statement.")]
        claims = [source_claim(docs[0], "capex_plan", 8000, "C2-A"),
                  source_claim(docs[1], "capex_plan", 5000, "C2-B")]
        observed = {"capex_plan": {"value": "5000", "unit": "USD_million", "fact_id": "C2-B"}}
        required = ["capex_plan"]
    elif case_id == "C3":
        docs = [source_record(case_id, "A", "FICE initial FY2025 capex plan: USD 8,000 million."),
                source_record(case_id, "B", "FICE formal correction: prior FY2025 capex plan of USD 8,000 million is superseded by USD 5,000 million.")]
        claims = [source_claim(docs[0], "capex_plan_initial", 8000, "C3-A"),
                  source_claim(docs[1], "capex_plan_corrected", 5000, "C3-B")]
        observed = {"capex_plan_corrected": {"value": "5000", "unit": "USD_million", "fact_id": "C3-B"}}
        required = ["capex_plan_corrected"]
    else:
        docs = []
        claims = []
        observed = {}
        required = ["capex_plan"]
    summary = ("FICE synthetic management evidence: " + " ".join(d["text"] for d in docs)
               if docs else "FICE synthetic secondary summary claims a new FY2025 capex plan, but the underlying primary source is unavailable.")
    return {"external_id": "synthetic-finance-16-" + case_id,
            "type": "management_update", "as_of": "2026-10-18",
            "summary": summary,
            "sources": [{k: d[k] for k in ("id", "url", "sha256")} for d in docs],
            "source_claims": claims, "observed_metrics": observed}, required, docs


def run_conflict(case_id, pilot):
    event, required, docs = conflict_event(case_id)
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "FICE", "title": "Synthetic capacity-plan thesis",
        "thesis": "Review the FY2025 capex plan using attributable primary evidence.",
        "status": "active", "conviction": 3,
        "required_event_metrics": required,
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
        "event_types": ["management_update"], "keywords": ["FICE"],
        "min_match_score": 1,
    }, pilot.tenant)
    alert = base.ingest(pilot, "FICE", event)["results"][0]["alert"]
    pilot.turn(
        "This is a synthetic research-state case. Read the stored thesis and alert. "
        "Compare the attributed management statements and dates; do not assume a "
        "later number silently supersedes an earlier one. Decide what is supported "
        "and what remains uncertain. Record a version-protected linked review, then "
        "acknowledge the alert. Do not trade. "
        f"Case {case_id}; thesis ID {thesis['id']}; alert ID {alert['id']}.")
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    current = state["theses"][0]["thesis"]
    stored = state["alerts"][0]["event"]
    held = case_id in ("C2", "C4")
    checks = {
        "one_review": len(reviews) == 1,
        "source_claims_exact": stored["sources"] == event["sources"] and
                               stored["source_claims"] == [
                                   {**claim, "value": str(claim["value"])}
                                   for claim in event["source_claims"]],
        "review_linked": len(reviews) == 1 and reviews[0]["alert_id"] == alert["id"],
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "hold_policy": (len(reviews) == 1 and reviews[0]["decision"] == "needs_review"
                        and current["status"] == "active" and current["conviction"] == 3)
                       if held else len(reviews) == 1 and not reviews[0]["missing_metrics"],
        "conflict_detection": bool(stored["unresolved_conflicts"]) == (case_id == "C2"),
        "actionability": (current["actionability"] == "blocked") if case_id in ("C2", "C4")
                         else (current["actionability"] == "available"),
    }
    rationale = normalized_numbers(review_text(state))
    if case_id in ("C1", "C2", "C3"):
        checks["claims_retained"] = "8000" in rationale and ("5000" in rationale if case_id != "C1" else True)
    return state, checks, {"synthetic_documents": docs}


def run_screen(case_id, pilot):
    tickers, condition = SCREEN[case_id]
    condition_text = (" Additional case evidence or policy: " + condition + ".") if condition else ""
    pilot.turn(
        "This is a synthetic, non-investment candidate-screening case. Call "
        "finance-tools__screen_stocks with require_complete=true for " + tickers + ". "
        "Read retained and rejected candidates." + condition_text +
        " Create a preliminary thesis only if the available evidence "
        "supports one; include exact tool values, missingness boundary, and synthetic "
        "provenance. Otherwise explain why no thesis is justified. Do not trade or "
        "call live market-data tools. Case " + case_id + ".")
    state = pilot.ledger_state()
    calls = [name for turn in pilot.turns for name in turn["tool_calls"]]
    theses = [entry["thesis"] for entry in state["theses"]]
    expected = "FICC" if case_id == "S1" else None
    checks = {
        "screen_called": "finance-tools__screen_stocks" in calls,
        "thesis_selection": len(theses) == (1 if expected else 0)
                            and (not expected or theses[0]["symbol"] == expected),
        "no_alerts": not state["alerts"],
        "no_trade_tool": all("trade" not in (name or "") for name in calls),
    }
    if expected and theses:
        text = normalized_numbers(theses[0]["thesis"]).lower()
        checks["exact_metrics_and_provenance"] = all(value in text for value in ("16.5", "310", "0.13")) and ("synthetic" in text or "fixture" in text)
    if case_id == "S3":
        final = normalized_numbers(final_text(pilot))
        checks["conflicting_values_explained"] = "420" in final and "260" in final
    return state, checks, {"synthetic_condition": condition}


def tool_payloads(pilot, name):
    payloads = []
    for turn in pilot.turns:
        for item in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []:
            if item.get("type") == "tool_call" and item.get("name") == name:
                try:
                    payloads.append(json.loads(item.get("arguments") or "{}"))
                except json.JSONDecodeError:
                    payloads.append(None)
    return payloads


def run_portfolio(case_id, pilot):
    text, expected_holdings, largest, breached = PORTFOLIO[case_id]
    pilot.turn(
        "This is a synthetic portfolio-risk diagnostic, not a live account. "
        "Available holdings: " + text + ". The single-holding concentration "
        "policy is breached only when a weight exceeds 50%; exactly 50% is at "
        "the limit, not above it. Use finance-tools__portfolio_risk with "
        "view=concentration if the complete portfolio is known. Explain the "
        "measured exposure or why it cannot be reliably computed. Do not infer "
        "a missing weight, trade, change holdings, or create ledger records. "
        "Case " + case_id + ".")
    state = pilot.ledger_state()
    payloads = tool_payloads(pilot, "finance-tools__portfolio_risk")
    final = normalized_numbers(final_text(pilot)).lower()
    checks = {"no_ledger_mutation": not state["theses"] and not state["alerts"]}
    if expected_holdings is None:
        checks["no_incomplete_calculation"] = not payloads
        checks["uncertainty_explained"] = any(word in final for word in
                                              ("missing", "unknown", "incomplete", "cannot", "insufficient"))
    else:
        checks["risk_tool_called"] = bool(payloads)
        checks["exact_holdings_submitted"] = any(
            isinstance(p, dict) and p.get("view") == "concentration" and
            p.get("holdings") == expected_holdings for p in payloads)
        checks["weight_and_limit_stated"] = str(int(largest)) in final and "50" in final
        checks["no_false_breach"] = not (case_id in ("P1", "P2") and
                                     any(phrase in final for phrase in
                                         ("limit is breached", "exceeds the limit", "breaches the limit")))
    return state, checks, {"expected_holdings": expected_holdings,
                           "expected_limit_breached": breached}


FUNCTIONS = {"E": (run_event, False), "C": (run_conflict, True),
             "S": (run_screen, True), "P": (run_portfolio, True)}


def preflight():
    if len(CASES) != 16 or len(set(CASES)) != 16:
        raise ValueError("panel must have 16 unique case IDs")
    for case_id in EVENTS:
        baseline, base_facts, current, current_facts, _ = EVENTS[case_id]
        for episode, facts in ((baseline, base_facts), (current, current_facts)):
            locked, _ = locked_episode(episode)
            available = {fact["id"] for fact in locked["facts"]}
            if not set(facts) <= available:
                raise ValueError(f"{case_id}: unknown SEC fact ID")
    for case_id in ("C1", "C2", "C3", "C4"):
        event, _, docs = conflict_event(case_id)
        if any(hashlib.sha256(d["text"].encode()).hexdigest() != d["sha256"] for d in docs):
            raise ValueError(f"{case_id}: synthetic source hash mismatch")
        if case_id == "C2" and len(set(c["source_sha256"] for c in event["source_claims"])) != 2:
            raise ValueError("C2 claims require distinct sources")
    for filename in ("stock_data.py", "portfolio_analytics.py"):
        if not list(previous.FIXTURES.rglob(filename)):
            raise FileNotFoundError(filename)
    with tempfile.TemporaryDirectory(prefix="finance-16-preflight-") as temp_root:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(temp_root) / "finance-tools.db"),
                           "finskillsPath": str(previous.FIXTURES),
                           "evaluationFixture": True})
        tenant = {"userId": "preflight-user", "agentId": "preflight-agent",
                  "sessionId": "preflight"}
        for case_id in ("C1", "C2", "C3", "C4"):
            case_tenant = {**tenant, "userId": "preflight-" + case_id}
            event, _, _ = conflict_event(case_id)
            thesis = must_call(plugin, "thesis_save", {
                "market": "US", "symbol": "FICE", "thesis": "Preflight synthetic case.",
                "status": "active", "conviction": 3}, case_tenant)["thesis"]
            must_call(plugin, "watchlist_save", {
                "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
                "event_types": ["management_update"], "keywords": ["FICE"]}, case_tenant)
            alert = must_call(plugin, "event_alert_ingest", {
                "market": "US", "symbol": "FICE", "event": event}, case_tenant)["results"][0]["alert"]
            if bool(alert["event"]["unresolved_conflicts"]) != (case_id == "C2"):
                raise ValueError(f"{case_id}: unexpected conflict classification")
        screened = must_call(plugin, "screen_stocks", {
            "market": "US", "symbols": ["FICC", "FICD"], "require_complete": True}, tenant)
        if not screened:
            raise ValueError("screen fixture is empty")
        risk = must_call(plugin, "portfolio_risk", {
            "holdings": {"FICA": 50, "FICB": 30, "FICC": 20},
            "view": "concentration"}, tenant)
        if not risk:
            raise ValueError("portfolio fixture is empty")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    preflight()
    if args.preflight_only:
        print(json.dumps({"cases": CASES, "preflight": "ok"}))
        return
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    base.MODEL, base.PRICING, base.CAP_USD = panel.MODEL, panel.PRICING, CAP_USD
    base.FIXTURES = previous.FIXTURES
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_finance_workflow_flash_panel_v1.py",
             HERE / "run_finance_workflow_pilot.py", HERE / "run_finance_workflow_v2.py",
             HERE / "run_thesis_event_panel.py", HERE / "run_thesis_event_gateway.py",
             HERE / "test_thesis_event_integration.py", HERE / "evidence.json",
             HERE / "source-lock.json", PLUGIN_PATH,
             *previous.FIXTURES.rglob("*.py")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(model=panel.MODEL, pricing=panel.PRICING, case_order=CASES,
                    gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    estimated_spend_stop_usd=CAP_USD,
                    observation_count_planned=16,
                    source_boundary="SEC cases source-locked; other cases synthetic")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-16-flash-") as temp_root:
        for case_id in CASES:
            if spent >= CAP_USD:
                print("STOP: estimated spend cap reached", flush=True)
                break
            function, synthetic = FUNCTIONS[case_id[0]]
            pilot = panel.PanelPilot(case_id, args.template_db, args.gateway_binary,
                                     temp_root, synthetic, spent)
            process, log = base.start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = function(case_id, pilot)
                trace, trace_details = panel.trace_checks(pilot)
                checks.update(trace)
                extras.update(trace=trace_details)
                checks["terminal_not_budget_exhausted"] = not any(
                    "maximum number of tool iterations" in
                    ((turn.get("response") or {}).get("choices") or [{}])[0]
                    .get("message", {}).get("content", "").lower()
                    for turn in pilot.turns)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                try:
                    state = pilot.ledger_state()
                except Exception:
                    pass
            finally:
                base.stop_gateway(process, log)
            spent += pilot.cost
            result = {"case_id": case_id, "workflow": case_id[0],
                      "synthetic_tool_fixture": synthetic,
                      "status": "mechanical_pass" if error is None and checks and all(checks.values()) else "needs_review",
                      "error": error, "checks": checks, "state": state,
                      "extras": extras, "turns": pilot.turns,
                      "estimated_cost_usd": pilot.cost}
            directory = args.output_dir / case_id
            directory.mkdir()
            (directory / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", directory / "finance-tools.db")
            print(json.dumps({"case_id": case_id, "status": result["status"],
                              "error": error, "checks": checks,
                              "estimated_cost_usd": pilot.cost}, ensure_ascii=False), flush=True)
            if error or any(not turn["priced_usage"] for turn in pilot.turns):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": spent}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
