#!/usr/bin/env python3
"""Verify the selected AXP Q2/Q3 rows against locked SEC exhibit bytes."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines
from selected_fact_delta_guard_v1 import derive


PACKET = ROOT / "axp_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
EXPECTED_UNITS = {
    "reported_billed_business": "USD_billion_reported",
    "gaap_total_revenues_net_of_interest_expense": "USD_million_rounded",
    "gaap_net_income": "USD_million_rounded",
    "gaap_diluted_eps": "USD_per_share_reported",
    "reported_average_diluted_common_shares": "million_shares_reported",
    "reported_principal_only_net_write_off_rate": "percent",
}
EXPECTED_DELTAS = {
    "reported_billed_business": "4.7",
    "gaap_total_revenues_net_of_interest_expense": "570",
    "gaap_net_income": "17",
    "gaap_diluted_eps": "0.06",
    "reported_average_diluted_common_shares": "-6",
    "reported_principal_only_net_write_off_rate": "-0.1",
}


def source_values(path, quarter: str) -> dict[str, Decimal]:
    lines = extract_lines(path)
    headline = " ".join(lines[:16])
    if (f"{quarter.upper()}-QUARTER" not in headline.upper()
            or "2025 2024" not in headline):
        raise ValueError("AXP earnings quarter/current-year header missing")
    head = lines[:22]
    values = {}
    rows = {
        "reported_billed_business": "Billed Business (Billions)FX-adjusted1",
        "gaap_total_revenues_net_of_interest_expense":
            "Total Revenues Net of Interest ExpenseFX-adjusted1",
        "gaap_net_income": "Net Income",
        "gaap_diluted_eps": "Diluted Earnings Per Common Share (EPS)2",
        "reported_average_diluted_common_shares":
            "Average Diluted Common Shares Outstanding",
    }
    for metric, label in rows.items():
        matching = [line for line in head if line.startswith(label + " ")]
        if len(matching) != 1:
            raise ValueError(f"AXP headline row missing or ambiguous: {label}")
        remainder = matching[0][len(label):]
        token = re.search(r"\$?\s*([\d,]+(?:\.\d+)?)", remainder)
        if not token:
            raise ValueError(f"AXP current-quarter value missing: {label}")
        values[metric] = Decimal(token.group(1).replace(",", ""))
    rate_phrase = (f"The {quarter.lower()}-quarter net write-off rate "
                   r"was\s+(\d+(?:\.\d+)?)\s+percent")
    rates = [match for line in lines[:28]
             if (match := re.search(rate_phrase, line, re.IGNORECASE))]
    if len(rates) != 1:
        raise ValueError("AXP current-quarter net write-off rate missing")
    if not any("Net write-off rates are based on principal losses only" in line
               for line in lines[:42]):
        raise ValueError("AXP principal-only ratio definition missing")
    values["reported_principal_only_net_write_off_rate"] = Decimal(rates[0].group(1))
    return values


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 2 or packet.get("symbol") != "AXP"
            or packet.get("cik") != "0000004962"):
        raise ValueError("unexpected AXP fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    for role, source_id, quarter in (
        ("baseline", "HOLDOUT-V2-AXP-BASELINE", "second"),
        ("event", "HOLDOUT-V2-AXP-EVENT", "third"),
    ):
        section, source = packet[role], entries[source_id]
        if any(section[field] != source[other] for field, other in (
                ("source_url", "url"), ("source_sha256", "sha256"),
                ("local_path", "local_path"))):
            raise ValueError(f"AXP source differs from lock: {role}")
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"AXP local source hash differs: {role}")
        current = source_values(path, quarter)
        facts = section["facts"]
        if len(facts) != 6 or len({fact["metric"] for fact in facts}) != 6:
            raise ValueError(f"AXP selected metric set differs: {role}")
        for fact in facts:
            metric = fact["metric"]
            if (metric not in current or fact["unit"] != EXPECTED_UNITS[metric]
                    or Decimal(str(fact["value"])) != current[metric]):
                raise ValueError(f"AXP SEC value or unit differs: {fact['id']}")
    bundle = derive(packet)
    deltas = {metric: row["delta_value"] for metric, row in bundle["rows"].items()}
    if deltas != EXPECTED_DELTAS:
        raise ValueError("AXP deterministic deltas differ from frozen oracle")
    return {
        "status": "selected_axp_rows_units_periods_and_deltas_match_locked_sec_sources",
        "selected_facts": 12,
        "comparisons": deltas,
        "ratio_delta_unit": bundle["rows"]["reported_principal_only_net_write_off_rate"]["delta_unit"],
        "model_observations": 0,
    }


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()),
                           json.loads(LOCK.read_text())), indent=2))
