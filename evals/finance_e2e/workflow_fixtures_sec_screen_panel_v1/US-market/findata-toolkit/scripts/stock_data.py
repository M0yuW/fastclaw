#!/usr/bin/env python3
"""Historical, source-locked SEC single-company screen adapter; never live data."""

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[4]
CASE = HERE / "sec_disclosure_screen_singleton_panel_v1.json"
SOURCE_LOCK = HERE / "source-lock.json"


def frozen_case():
    case = json.loads(CASE.read_text())
    entries = {entry["id"]: entry for entry in json.loads(SOURCE_LOCK.read_text())["entries"]}
    for candidate in case["candidates"]:
        entry = entries[candidate["source_id"]]
        if (entry["url"] != candidate["source_url"] or
                entry["sha256"] != candidate["source_sha256"] or
                hashlib.sha256((HERE / entry["local_path"]).read_bytes()).hexdigest() != entry["sha256"]):
            raise ValueError("SEC source-lock mismatch for " + candidate["symbol"])
    return case


def screen(case, symbols):
    criteria = case["criteria"]
    results, rejected = [], []
    for candidate in case["candidates"]:
        if candidate["symbol"] not in symbols:
            continue
        facts = candidate["reported"]
        failures = []
        if facts["gaap_gross_margin_percent"] < criteria["gaap_gross_margin_min_percent"]:
            failures.append("gaap_gross_margin_below_threshold")
        if facts["revenue_yoy_percent"] < criteria["revenue_yoy_min_percent"]:
            failures.append("revenue_yoy_below_threshold")
        if failures:
            rejected.append({**candidate, "reason": "disclosure_criteria_not_met",
                             "failed_criteria": failures})
        else:
            results.append(candidate)
    return {
        "fixture_id": case["panel_id"], "synthetic": False,
        "offline_frozen_adapter": True, "not_live_market_data": True,
        "scope": case["scope"], "criteria": criteria,
        "excluded_dimensions": case["excluded_dimensions"],
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
