#!/usr/bin/env python3
"""Run the neutral-ID, source-locked event-to-thesis Gateway panel.

Each observation uses an isolated Gateway snapshot, empty finance ledger,
ephemeral API key, and new session. This never edits earlier experiment runs.
"""

import argparse
import json
import os
import shutil
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from run_thesis_event_gateway import create_ephemeral_key, load_plugin, must_call
from run_thesis_event_panel import (
    AGENT_ID, HERE, PORT, PLUGIN_PATH, ROOT, metric_text, prepare_home,
    sha256, source_ref, start_gateway, stop_gateway,
)
from test_thesis_event_integration import locked_episode

SUITE = HERE / "thesis_event_panel_v2.json"


def validate_suite(suite):
    if suite["suite_id"] != "thesis-event-panel-v2":
        raise ValueError("unexpected suite ID")
    cases = {case["id"]: case for case in suite["cases"]}
    if set(cases) != {"C01", "C02", "C03", "C04"}:
        raise ValueError("case identifiers must be neutral C01-C04")
    expected_runs = {f"{case_id}-r{rep}" for case_id in cases
                     for rep in range(1, suite["repetitions_per_case"] + 1)}
    if len(suite["run_order"]) != len(expected_runs) or set(suite["run_order"]) != expected_runs:
        raise ValueError("run order must contain every assigned observation exactly once")
    for case in cases.values():
        before, _ = locked_episode(case["baseline_episode"])
        after, _ = locked_episode(case["event_episode"])
        if before["symbol"] != after["symbol"] or before["symbol"] != case["symbol"]:
            raise ValueError(f"issuer mismatch in {case['id']}")
        baseline = {fact["id"] for fact in before["facts"]}
        event = {fact["id"] for fact in after["facts"]}
        if not set(case["baseline_metrics"]) <= baseline or not set(case["event_metrics"]) <= event:
            raise ValueError(f"unknown evidence ID in {case['id']}")
        packet_metrics = {fact["metric"] for fact in after["facts"]
                          if fact["id"] in case["event_metrics"]}
        missing = set(case["required_event_metrics"]) - packet_metrics
        expected_missing = set(case["oracle"].get("required_missing_metrics", []))
        if missing != expected_missing:
            raise ValueError(f"missing-metric oracle mismatch in {case['id']}")
        if case["id"] == "C03" and not (
            case["baseline_label"].startswith("Q4 FY") and case["event_label"].startswith("Q4 FY")
        ):
            raise ValueError("C03 must use matching fiscal quarters")
    return cases


def prompt_for(case_id, thesis_id, alert_id):
    return (
        "Review the stored research thesis against the newly ingested SEC event packet. "
        "This is a research-state workflow, not investment advice. Use "
        "finance-tools__thesis_get and finance-tools__alert_list to read the "
        "baseline, required metrics, event observations, and source reference. "
        "Compute relevant changes using the correct periods and units; distinguish "
        "source facts, calculations, and uncertainty. Decide the impact, review "
        "decision, status, and conviction yourself from the evidence and stored "
        "thesis conditions. Record one successful review with the observed thesis "
        "version, linked alert_id, and SEC source ID/hash. If the ledger rejects a "
        "review for missing required metrics, correct the decision and retry at most "
        "once; do not claim a missing packet field is missing from the SEC filing. "
        "Then acknowledge the alert using its observed version. Do not trade or "
        "change a portfolio. "
        f"Case {case_id}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


def run_observation(case, run_id, suite, template_db, binary, temporary_root):
    home = prepare_home(template_db, binary, temporary_root)
    with sqlite3.connect(home / "fastclaw.db") as connection:
        row = connection.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
        config = json.loads(row[0])
        config["maxToolIterations"] = 8
        connection.execute("UPDATE agents SET config=? WHERE id=?", (json.dumps(config), AGENT_ID))
    baseline, baseline_source = locked_episode(case["baseline_episode"])
    episode, event_source = locked_episode(case["event_episode"])
    token, user_id = create_ephemeral_key(home / "fastclaw.db", AGENT_ID)
    tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "fixture-seed"}
    finance = load_plugin().FinanceToolsPlugin()
    finance.initialize({"stateDbPath": str(home / "finance-tools.db")})
    if must_call(finance, "thesis_list", {}, tenant)["count"]:
        raise ValueError("expected an empty isolated finance ledger")
    thesis = must_call(finance, "thesis_save", {
        "market": "US", "symbol": case["symbol"], "title": f"{case['symbol']} filing research thesis",
        "thesis": f"{case['baseline_label']} SEC baseline: "
                  f"{metric_text(baseline, case['baseline_metrics'])}. {case['seed_thesis']}",
        "status": "active", "conviction": 3,
        "catalysts": case["seed_catalysts"], "invalidations": case["seed_invalidations"],
        "required_event_metrics": case["required_event_metrics"],
        "evidence": [source_ref(baseline_source)],
    }, tenant)["thesis"]
    must_call(finance, "watchlist_save", {
        "market": "US", "symbol": case["symbol"], "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [case["symbol"]], "min_match_score": 1,
    }, tenant)
    fact_by_id = {fact["id"]: fact for fact in episode["facts"]}
    observed = {
        fact_by_id[fact_id]["metric"]: {
            "value": fact_by_id[fact_id]["value"],
            "unit": fact_by_id[fact_id]["unit"],
            "fact_id": fact_id,
        }
        for fact_id in case["event_metrics"]
    }
    event = {
        "external_id": episode["source_id"], "type": "earnings", "as_of": episode["observed_at"],
        "summary": f"{case['symbol']} {case['event_label']} SEC event packet: "
                   f"{metric_text(episode, case['event_metrics'])}.",
        "sources": [source_ref(event_source)], "observed_metrics": observed,
    }
    ingested = must_call(finance, "event_alert_ingest", {
        "market": "US", "symbol": case["symbol"], "event": event,
    }, tenant)
    if ingested["created"] != 1:
        raise AssertionError("expected one alert from a fresh event")
    alert = ingested["results"][0]["alert"]
    prompt = prompt_for(case["id"], thesis["id"], alert["id"])
    for forbidden in ("deterioration", "positive_change", "benefit_and_risk", "conviction 3"):
        if forbidden in prompt.lower():
            raise AssertionError("outcome label leaked into prompt")
    request_body = {
        "messages": [{"role": "user", "content": prompt}], "stream": False,
        "fastclaw": {"eval": True, "include_trace": True, "include_usage_breakdown": True,
                     "server_timeout_ms": 120000,
                     "pricing": suite["pricing_usd_per_million_tokens"]},
    }
    process, log = start_gateway(home)
    response, error = None, None
    started = time.monotonic()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions",
            data=json.dumps(request_body).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                     "x-fastclaw-agent-id": AGENT_ID,
                     "x-fastclaw-session-key": "finance-v2-" + run_id}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=150) as handle:
                response = json.load(handle)
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read(2048).decode(errors='replace')}"
        except (urllib.error.URLError, TimeoutError) as exc:
            error = str(exc)
    finally:
        elapsed = time.monotonic() - started
        stop_gateway(process, log)
    fetched = must_call(finance, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
    reviews, actual = fetched["reviews"], fetched["thesis"]
    alerts = must_call(finance, "alert_list", {"symbol": case["symbol"]}, tenant)["alerts"]
    review = reviews[0] if len(reviews) == 1 else None
    model_calls = (response or {}).get("fastclaw", {}).get("model_calls", [])
    trace = (response or {}).get("fastclaw", {}).get("trace", [])
    tool_calls = [item.get("name") for item in trace if item.get("type") == "tool_call"]
    expected_missing = case["oracle"].get("required_missing_metrics", [])
    checks = {
        "one_review": len(reviews) == 1,
        "version_once": actual["version"] == thesis["version"] + 1,
        "linked_alert": bool(review) and review.get("alert_id") == alert["id"],
        "source_recorded": bool(review) and any(
            source.get("id") == event_source["id"] and source.get("sha256") == event_source["sha256"]
            for source in review["event"].get("sources", [])),
        "alert_acknowledged": len(alerts) == 1 and alerts[0]["status"] == "acknowledged",
        "priced_usage": bool(model_calls) and all(call.get("priced") is True for call in model_calls),
        "model_matches_suite": bool(response) and response.get("model") == suite["model"],
        "decision_in_predeclared_set": bool(review) and review["decision"] in case["oracle"]["acceptable_decisions"],
        "status_in_predeclared_set": actual["status"] in case["oracle"]["acceptable_statuses"],
        "missing_metrics_recorded": bool(review) and review.get("missing_metrics") == expected_missing,
        "no_trade_tool": all("trade" not in name and "portfolio" not in name for name in tool_calls if name),
    }
    result = {
        "run_id": run_id, "case_id": case["id"],
        "status": "mechanical_pass" if error is None and all(checks.values()) else "needs_review",
        "error": error, "elapsed_seconds": round(elapsed, 3), "checks": checks,
        "seed": {"baseline_episode": case["baseline_episode"], "event_episode": case["event_episode"],
                 "baseline_source": source_ref(baseline_source), "event_source": source_ref(event_source),
                 "initial_status": thesis["status"], "initial_conviction": thesis["conviction"],
                 "initial_version": thesis["version"], "required_event_metrics": case["required_event_metrics"]},
        "event_packet": event, "prompt": prompt,
        "review": review,
        "after": {"version": actual["version"], "status": actual["status"],
                  "conviction": actual["conviction"], "reviews": len(reviews),
                  "alert_statuses": [item["status"] for item in alerts]},
        "tool_calls": tool_calls,
        "model_calls": len(model_calls),
        "estimated_cost_usd": sum(call.get("estimated_cost_usd", 0) for call in model_calls),
        "gateway_response": response,
        "manual_semantic_audit_pending": True,
    }
    return result, home


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    cases = validate_suite(suite)
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("isolated Gateway template DB and binary required")
    args.output_dir.mkdir(parents=True)
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in (
        SUITE, Path(__file__), HERE / "run_thesis_event_panel.py",
        HERE / "run_thesis_event_gateway.py", HERE / "test_thesis_event_integration.py",
        HERE / "evidence.json", HERE / "source-lock.json", PLUGIN_PATH,
        ROOT / "internal/policy/defaults.go", ROOT / "internal/plugin/tool_adapter.go",
    )}
    manifest["gateway_binary_sha256"] = sha256(args.gateway_binary)
    manifest["gateway_template_db_sha256"] = sha256(args.template_db)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total_estimate = 0.0
    with tempfile.TemporaryDirectory(prefix="thesis-panel-v2-") as temporary_root:
        for run_id in suite["run_order"]:
            case = cases[run_id.split("-r")[0]]
            result, home = run_observation(case, run_id, suite, args.template_db,
                                           args.gateway_binary, temporary_root)
            attempt_dir = args.output_dir / run_id
            attempt_dir.mkdir()
            (attempt_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(home / "finance-tools.db", attempt_dir / "finance-tools.db")
            total_estimate += result["estimated_cost_usd"]
            print(json.dumps({"run_id": run_id, "status": result["status"],
                              "error": result["error"], "checks": result["checks"],
                              "estimated_cost_usd": result["estimated_cost_usd"]}, ensure_ascii=False), flush=True)
            if not result["checks"]["priced_usage"] or result["error"] or total_estimate >= suite["estimated_spend_stop_usd"]:
                print("STOP: uncertain pricing, request error, or estimated spend cap reached", flush=True)
                break
    print(json.dumps({"completed": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": total_estimate}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
