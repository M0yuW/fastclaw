#!/usr/bin/env python3
"""Read-only adjudication of one retained live Skill-to-thesis observation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events(result: dict, kind: str) -> list[dict]:
    return [event for turn in result["turns"]
            for event in turn["response"]["fastclaw"]["trace"]
            if event.get("type") == kind]


def adjudicate(result_path: Path, ledger_path: Path) -> dict:
    raw = json.loads(result_path.read_text())
    source = raw["retrieved"]
    first, last = source["prices"][0], source["prices"][-1]
    expected_percent = (last["close"] / first["close"] - 1) * 100
    calls, responses = events(raw, "tool_call"), events(raw, "tool_result")
    parsed_calls = [(event["name"], json.loads(event.get("arguments") or "{}"))
                    for event in calls]
    skill_script = raw["skill_script"]
    market_fetches = [arguments for name, arguments in parsed_calls
                      if name == "exec" and skill_script in arguments.get("command", "")]
    thesis_saves = [arguments for name, arguments in parsed_calls
                    if name == "finance-tools__thesis_save"]
    thesis_rows = raw["state"]["theses"]
    thesis = thesis_rows[0]["thesis"] if len(thesis_rows) == 1 else {}
    evidence = thesis.get("evidence", [])
    price_evidence = [item for item in evidence
                      if isinstance(item, dict) and item.get("type") == "price_history"]
    record = price_evidence[0] if len(price_evidence) == 1 else {}
    percent = record.get("close_change_percent", record.get("computed_change_percent"))
    ledger_uri = f"file:{ledger_path}?mode=ro&immutable=1"
    with sqlite3.connect(ledger_uri, uri=True) as db:
        ledger_counts = {table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("theses", "event_alerts", "thesis_reviews")}
    checks = {
        "single_skill_market_fetch": len(market_fetches) == 1
            and "AMD --history --period 5d --source nasdaq" in market_fetches[0].get("command", ""),
        "single_thesis_save": len(thesis_saves) == 1,
        "no_other_tool_family": all(name in {"exec", "finance-tools__thesis_save"}
                                    for name, _ in parsed_calls),
        "paired_tool_results": sorted(event.get("id") for event in calls)
                                == sorted(event.get("id") for event in responses),
        "no_tool_result_error": all(not event.get("error") for event in responses),
        "one_isolated_ledger_record": ledger_counts == {
            "theses": 1, "event_alerts": 0, "thesis_reviews": 0},
        "preliminary_research_state": thesis.get("symbol") == "AMD"
            and thesis.get("status") == "researching" and thesis.get("conviction") == 1,
        "source_provenance": record.get("source_url") == source.get("source_url")
            and record.get("source_name") == source.get("source"),
        "endpoint_facts": record.get("first_bar_date") == first.get("date")
            and record.get("latest_bar_date") == last.get("date")
            and record.get("first_bar_close") == first.get("close")
            and record.get("latest_bar_close") == last.get("close")
            and record.get("interval") == source.get("interval") == "1d",
        "return_arithmetic": isinstance(percent, (int, float))
            and math.isclose(percent, expected_percent, abs_tol=0.02),
        "priced_under_cap": raw["estimated_cost_usd"] < raw["cost_cap_usd"]
            and all(turn["priced_usage"] for turn in raw["turns"]),
    }
    return {
        "status": "workflow_pass" if all(checks.values()) else "needs_review",
        "original_status": raw["status"],
        "checks": checks,
        "ledger_counts": ledger_counts,
        "source_first_close": first["close"],
        "source_latest_close": last["close"],
        "independent_change_percent": expected_percent,
        "recorded_change_percent": percent,
        "decision_hold": thesis.get("decision_hold"),
        "actionability": thesis.get("actionability"),
        "result_sha256": sha256(result_path),
        "ledger_sha256": sha256(ledger_path),
        "scope": "execution, provenance, arithmetic and isolated ledger only; not prose or investment quality",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; refusing to overwrite")
    report = adjudicate(args.result, args.ledger)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"status": report["status"], "checks": report["checks"]}))
    return 0 if report["status"] == "workflow_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
