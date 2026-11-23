#!/usr/bin/env python3
"""Read-only, schema-tolerant audit of a frozen SEC screen result."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


FACTS = {
    "gaap_revenue_usd_million": ("AMD-Q3-REV", 6819),
    "revenue_yoy_percent": ("AMD-Q3-REV-YOY", 18),
    "gaap_gross_margin_percent": ("AMD-Q3-GM", 50),
    "gaming_revenue_usd_million": ("AMD-Q3-GAME", 462),
    "gaming_revenue_yoy_percent": ("AMD-Q3-GAME-YOY", -69),
}


def source_matches(record, candidate):
    return (record.get("source_url") == candidate["source_url"] and
            record.get("source_sha256") == candidate["source_sha256"])


def fact_is_saved(evidence, candidate, metric, fact_id, value):
    for record in evidence:
        if not isinstance(record, dict) or not source_matches(record, candidate):
            continue
        nested = record.get("reported_values") or {}
        if isinstance(nested, dict) and nested.get(metric) == value:
            units = str(record.get("units") or "").lower()
            if "usd million" in units and "percent" in units:
                return True
        if record.get("evidence_id") == fact_id and record.get("value") == value:
            unit = str(record.get("unit") or "").lower()
            if ("percent" in metric and unit == "percent") or (
                    "usd_million" in metric and unit == "usd million"):
                return True
    return False


def schedule_valid(value):
    if not value:
        return True
    try:
        when = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc) > datetime.now(timezone.utc)


def audit(result, case):
    amd = next(item for item in case["candidates"] if item["symbol"] == "AMD")
    intel = next(item for item in case["candidates"] if item["symbol"] == "INTC")
    state = result.get("state") or {}
    theses = [entry["thesis"] for entry in state.get("theses") or []]
    thesis = theses[0] if len(theses) == 1 else {}
    evidence = thesis.get("evidence") or []
    payload = (result.get("extras") or {}).get("screen_tool_payload") or {}
    data = payload.get("data") or {}
    calls = [name for turn in result.get("turns") or [] for name in turn.get("tool_calls") or []]
    final = "\n".join(
        ((turn.get("response") or {}).get("choices") or [{}])[0]
        .get("message", {}).get("content", "") for turn in result.get("turns") or []
    ).lower()
    record_text = json.dumps(thesis, ensure_ascii=False).lower()
    checks = {
        "screen_retained_amd_rejected_intc":
            [item.get("symbol") for item in data.get("results") or []] == ["AMD"] and
            [item.get("symbol") for item in data.get("rejected") or []] == ["INTC"] and
            (data.get("rejected") or [{}])[0].get("source_sha256") == intel["source_sha256"],
        "paired_runtime_tool_calls":
            calls.count("finance-tools__screen_stocks") == 1 and
            calls.count("finance-tools__thesis_save") == 1 and
            (result.get("runtime_audit") or {}).get("tool_calls_paired") is True,
        "one_amd_thesis_no_intel_thesis": len(theses) == 1 and thesis.get("symbol") == "AMD",
        "all_five_values_units_and_sec_source_saved": all(
            fact_is_saved(evidence, amd, metric, fact_id, value)
            for metric, (fact_id, value) in FACTS.items()),
        "risk_and_historical_scope_saved":
            all(term in record_text for term in ("gaming", "462", "69", "historical",
                                                   "preliminary", "valuation")),
        "intel_rejection_explained":
            all(term in final for term in ("intel", "15.0%", "6%", "rejected")),
        "no_trade_or_live_market_call":
            not state.get("alerts") and all(
                "trade" not in (name or "") and "stock_snapshot" not in (name or "")
                for name in calls),
        "priced_clean_request":
            (result.get("runtime_audit") or {}).get("clean_completion") is True and
            (result.get("checks") or {}).get("usage_priced") is True and
            not result.get("error"),
        "operational_next_review_date": schedule_valid(thesis.get("next_review_at")),
    }
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    raw = args.result.read_bytes()
    result = json.loads(raw)
    checks = audit(result, json.loads(args.case.read_text()))
    print(json.dumps({"result_sha256": hashlib.sha256(raw).hexdigest(),
                      "raw_status": result.get("status"),
                      "checks": checks, "passed": sum(checks.values()),
                      "total": len(checks)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
