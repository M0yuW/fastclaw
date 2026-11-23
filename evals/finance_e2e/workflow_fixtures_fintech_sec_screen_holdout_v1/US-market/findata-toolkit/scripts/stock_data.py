#!/usr/bin/env python3
"""Offline SEC-source-locked screen adapter; never a live market feed."""

import hashlib
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parents[4]
CASE = HERE / "fintech_sec_screen_holdout_v1.json"


def frozen_case():
    case = json.loads(CASE.read_text())
    if case["panel_id"] != "FINTECH-SEC-SCREEN-HOLDOUT-v1":
        raise ValueError("wrong frozen case")
    for candidate in case["candidates"]:
        source = HERE / candidate["local_path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != candidate["source_sha256"]:
            raise ValueError("SEC source hash mismatch for " + candidate["symbol"])
    return case


def screen(case, symbols):
    threshold = case["criteria"]["reported_top_line_revenue_yoy_min_percent"]
    results, rejected = [], []
    for candidate in case["candidates"]:
        if candidate["symbol"] not in symbols:
            continue
        facts = candidate["reported"]
        growth = facts.get("top_line_revenue_yoy_percent_reported",
                           facts.get("top_line_revenue_yoy_percent_derived"))
        failures = [] if growth >= threshold else ["reported_top_line_revenue_yoy_below_threshold"]
        public = {key: value for key, value in candidate.items() if key != "oracle_retain"}
        if failures:
            rejected.append({**public, "reason": "disclosure_criteria_not_met",
                             "failed_criteria": failures})
        else:
            results.append(public)
    return {
        "fixture_id": case["panel_id"], "synthetic": False,
        "offline_frozen_adapter": True, "not_live_market_data": True,
        "scope": case["scope"], "basis_warning": case["basis_warning"],
        "criteria": case["criteria"], "excluded_dimensions": case["excluded_dimensions"],
        "results": results, "rejected": rejected,
        "passed": len(results), "failed": len(rejected),
    }


def main():
    if "--screen" not in sys.argv:
        raise SystemExit("offline adapter supports --screen only")
    case = frozen_case()
    available = {item["symbol"] for item in case["candidates"]}
    requested = {arg.upper() for arg in sys.argv[1:] if arg.upper() in available}
    if not requested:
        raise SystemExit("request one of the frozen symbols")
    print(json.dumps(screen(case, requested), separators=(",", ":")))


if __name__ == "__main__":
    main()
