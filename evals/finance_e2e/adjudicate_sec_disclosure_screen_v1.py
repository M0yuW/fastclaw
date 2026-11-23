#!/usr/bin/env python3
"""Read-only post-run audit; does not rewrite the sealed one-shot result."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result", type=Path)
    parser.add_argument("case", type=Path)
    args = parser.parse_args()
    raw = args.result.read_bytes()
    result = json.loads(raw)
    case = json.loads(args.case.read_text())
    amd = next(item for item in case["candidates"] if item["symbol"] == "AMD")
    intel = next(item for item in case["candidates"] if item["symbol"] == "INTC")
    theses = [entry["thesis"] for entry in (result.get("state") or {}).get("theses") or []]
    thesis = theses[0] if len(theses) == 1 else {}
    evidence = thesis.get("evidence") or []
    facts = {item.get("evidence_id"): item for item in evidence if isinstance(item, dict)}
    required = {
        "AMD-Q3-REV": (6819, "USD million"),
        "AMD-Q3-REV-YOY": (18, "percent"),
        "AMD-Q3-GM": (50, "percent"),
        "AMD-Q3-GAME": (462, "USD million"),
        "AMD-Q3-GAME-YOY": (-69, "percent"),
    }
    fact_check = all(
        facts.get(key, {}).get("value") == value and
        facts.get(key, {}).get("unit") == unit and
        facts.get(key, {}).get("source_url") == amd["source_url"] and
        facts.get(key, {}).get("source_sha256") == amd["source_sha256"]
        for key, (value, unit) in required.items()
    )
    payload = (result.get("extras") or {}).get("screen_tool_payload") or {}
    data = payload.get("data") or {}
    calls = [name for turn in result.get("turns") or [] for name in turn.get("tool_calls") or []]
    final = "\n".join(
        ((turn.get("response") or {}).get("choices") or [{}])[0]
        .get("message", {}).get("content", "") for turn in result.get("turns") or []
    ).lower()
    full_record = json.dumps(thesis, ensure_ascii=False).lower()
    checks = {
        "screen_retained_and_rejected":
            [item.get("symbol") for item in data.get("results") or []] == ["AMD"] and
            [item.get("symbol") for item in data.get("rejected") or []] == ["INTC"] and
            data.get("rejected", [{}])[0].get("source_sha256") == intel["source_sha256"],
        "one_real_tool_screen_and_one_thesis_save":
            calls.count("finance-tools__screen_stocks") == 1 and
            calls.count("finance-tools__thesis_save") == 1,
        "one_amd_record_no_intel_record": len(theses) == 1 and thesis.get("symbol") == "AMD",
        "five_amd_facts_with_units_and_sec_hash": fact_check,
        "gaming_risk_and_scope_in_persisted_record":
            "462" in full_record and "69" in full_record and
            "gaming" in full_record and
            all(term in full_record for term in ("historical", "preliminary", "valuation")),
        "intel_rejection_explained_to_user":
            all(term in final for term in ("intel", "15.0%", "6%", "rejected")),
        "no_trade_or_live_market_tool":
            not (result.get("state") or {}).get("alerts") and
            all("trade" not in (name or "") and
                "stock_snapshot" not in (name or "") for name in calls),
        "runtime_completion_and_priced_usage":
            (result.get("runtime_audit") or {}).get("clean_completion") is True and
            (result.get("checks") or {}).get("usage_priced") is True and
            not result.get("error"),
    }
    print(json.dumps({"result_sha256": hashlib.sha256(raw).hexdigest(),
                      "raw_mechanical_status": result.get("status"),
                      "post_run_checks": checks,
                      "all_post_run_checks_pass": all(checks.values()),
                      "raw_failure_is_body_only_numeric_oracle":
                          (result.get("checks") or {}).get("reported_values_and_risk") is False and
                          fact_check,
                      "estimated_cost_usd": result.get("estimated_cost_usd")},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
