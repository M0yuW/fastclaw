#!/usr/bin/env python3
"""Audit OneMain's selected GAAP and C&I credit-ratio facts against SEC exhibits."""

from __future__ import annotations

import copy
import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines
from sec_inline_table import first_column_value


PACKET = ROOT / "omf_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
STATEMENT_START = "CONSOLIDATED STATEMENTS OF OPERATIONS (UNAUDITED)"
STATEMENT_END = "Weighted average number of diluted shares"
RATIO_START = "C&I Select Delinquency and Loss Ratios"
RATIO_END = "Operating expense for the"


def ratio_cell(lines: list[str], fact: dict, expected_date: str) -> Decimal:
    starts = [i for i, line in enumerate(lines) if RATIO_START in line]
    if len(starts) != 1 or expected_date not in lines[starts[0]]:
        raise ValueError(f"credit-ratio table/date missing: {fact['id']}")
    start = starts[0]
    stop = next((i for i in range(start + 1, len(lines)) if RATIO_END in lines[i]), None)
    if stop is None:
        raise ValueError("credit-ratio section end missing")
    rows = [line for line in lines[start:stop] if line.startswith(fact["source_row"] + " ")]
    if len(rows) != 1:
        raise ValueError(f"credit-ratio row missing or ambiguous: {fact['id']}")
    values = re.findall(r"(\d+(?:\.\d+)?)\s*%", rows[0][len(fact["source_row"]):])
    if len(values) < 3:
        raise ValueError(f"credit-ratio row has too few columns: {fact['id']}")
    return Decimal(values[0])


def audit(packet: dict, lock: dict) -> dict:
    if packet.get("version") != 1 or packet.get("symbol") != "OMF":
        raise ValueError("unexpected OneMain fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    for period, source_id, month in (("baseline", "HOLDOUT-OMF-BASELINE-v1", "Jun"),
                                     ("event", "HOLDOUT-OMF-EVENT-v1", "Sep")):
        section, source = packet[period], entries[source_id]
        if (section["source_url"] != source["url"] or
                section["source_sha256"] != source["sha256"] or
                section["local_path"] != source["local_path"]):
            raise ValueError(f"fact packet source differs from lock: {period}")
        lines = extract_lines(ROOT / source["local_path"])
        full_month = "June" if month == "Jun" else "September"
        for fact in section["facts"]:
            if fact["unit"] == "percent":
                actual = ratio_cell(lines, fact, f"{full_month} 30, 2025")
                if actual != Decimal(str(fact["value"])):
                    raise ValueError(f"selected credit-ratio row differs: {fact['id']}")
            elif fact["unit"] == "USD_million_rounded":
                actual = first_column_value(
                    lines, start_anchor=STATEMENT_START, end_anchor=STATEMENT_END,
                    row_label=fact["source_row"],
                    header_fragments=("Quarter Ended Fiscal Year", f"{month} 30", "2025"),
                    min_columns=7)
                if fact.get("normalization") == "absolute_value_of_parenthesized_expense_cell":
                    if actual >= 0:
                        raise ValueError(f"expense cell is not parenthesized: {fact['id']}")
                    actual = abs(actual)
                elif fact.get("normalization"):
                    raise ValueError(f"unknown normalization: {fact['id']}")
                if actual != fact["value"]:
                    raise ValueError(f"selected GAAP row differs: {fact['id']}")
            else:
                raise ValueError(f"unsupported fact unit: {fact['id']}")
    monetary = copy.deepcopy(packet)
    for period in ("baseline", "event"):
        monetary[period]["facts"] = [fact for fact in monetary[period]["facts"]
                                     if fact["unit"] != "percent"]
    bundle = build_bundle(monetary)
    money_deltas = {item["metric"]: int(item["delta_usd_thousand"]) // 1000
                    for item in bundle["comparisons"]}
    expected_money = {"gaap_net_interest_income": 50, "gaap_net_income": 32,
                      "gaap_provision_expense_magnitude": -23,
                      "gaap_operating_expense_magnitude": 17}
    if money_deltas != expected_money:
        raise ValueError("monetary comparisons differ from frozen oracle")
    baseline_rates = {fact["metric"]: Decimal(str(fact["value"]))
                      for fact in packet["baseline"]["facts"] if fact["unit"] == "percent"}
    event_rates = {fact["metric"]: Decimal(str(fact["value"]))
                   for fact in packet["event"]["facts"] if fact["unit"] == "percent"}
    rate_points = {metric: str(value - baseline_rates[metric])
                   for metric, value in event_rates.items()}
    expected_rates = {"ci_consumer_30_plus_delinquency_ratio": "0.38",
                      "ci_consumer_90_plus_delinquency_ratio": "0.23",
                      "ci_consumer_net_charge_off_ratio": "-0.52"}
    if rate_points != expected_rates:
        raise ValueError("ratio-point comparisons differ from frozen oracle")
    return {"status": "selected_onemain_rows_and_rate_deltas_match_locked_sec_sources",
            "selected_facts": 14, "monetary_deltas_usd_million": money_deltas,
            "ratio_deltas_percentage_points": rate_points,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, lock), indent=2))
