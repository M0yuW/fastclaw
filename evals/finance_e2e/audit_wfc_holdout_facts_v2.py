#!/usr/bin/env python3
"""Audit WFC's selected company-wide Q2/Q3 facts and mixed-basis margin."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines
from selected_fact_delta_guard_v1 import decompose_change, derive


PACKET = ROOT / "wfc_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
EXPECTED_DELTAS = {
    "gaap_net_interest_income": "242",
    "gaap_noninterest_income": "372",
    "gaap_total_revenue": "614",
    "reported_net_charge_offs": "-43",
    "gaap_provision_for_credit_losses": "-324",
    "gaap_noninterest_expense": "467",
    "gaap_income_tax_expense": "384",
    "gaap_wells_fargo_net_income": "95",
    "fte_net_interest_margin": "-0.07",
}


def selected_rows(path, quarter_header):
    lines = extract_lines(path)
    starts = [i for i, line in enumerate(lines)
              if line.endswith("Selected Company-wide Financial Information")]
    if len(starts) != 1 or quarter_header not in " ".join(lines[starts[0]:starts[0] + 5]):
        raise ValueError("WFC company-wide quarter header differs")
    starts_earnings = [i for i in range(starts[0], min(starts[0] + 30, len(lines)))
                       if lines[i].startswith("Earnings ($ in millions")]
    starts_balance = [i for i in range(starts[0], min(starts[0] + 40, len(lines)))
                      if lines[i].startswith("Balance Sheet Data (average)")]
    if len(starts_earnings) != 1 or len(starts_balance) != 1:
        raise ValueError("WFC selected earnings table boundaries differ")
    section = lines[starts_earnings[0] + 1:starts_balance[0]]
    ratios_start = [i for i in range(starts_balance[0], min(starts_balance[0] + 30, len(lines)))
                    if lines[i] == "Financial Ratios"]
    if len(ratios_start) != 1:
        raise ValueError("WFC selected ratios heading differs")
    ratios = lines[ratios_start[0] + 1:ratios_start[0] + 12]
    return section, ratios


def reported_columns(lines, row_label):
    matching = [line for line in lines if line.startswith(row_label + " ")]
    if len(matching) != 1:
        raise ValueError(f"WFC selected SEC row missing or ambiguous: {row_label}")
    values = re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?",
                        matching[0][len(row_label):])
    if len(values) < 3:
        raise ValueError(f"WFC reported quarter columns missing: {row_label}")
    return tuple(Decimal(value.replace(",", "").strip("()"))
                 * (-1 if value.startswith("(") else 1) for value in values[:3])


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 2 or packet.get("symbol") != "WFC"
            or packet.get("cik") != "0000072971"):
        raise ValueError("unexpected WFC fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    selected = {}
    source_rows = {}
    for role, source_id, header in (
        ("baseline", "HOLDOUT-V2-WFC-BASELINE", "Quarter ended Jun 30, 2025"),
        ("event", "HOLDOUT-V2-WFC-EVENT", "Quarter ended Sep 30, 2025"),
    ):
        section, source = packet[role], entries[source_id]
        if (section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"WFC source differs from lock: {role}")
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"WFC local source hash differs: {role}")
        earnings, ratios = selected_rows(path, header)
        facts = section["facts"]
        if len(facts) != 9 or len({fact["metric"] for fact in facts}) != 9:
            raise ValueError(f"WFC selected metric set differs: {role}")
        selected[role] = {}
        source_rows[role] = {}
        for fact in facts:
            expected_unit = "percent" if fact["metric"] == "fte_net_interest_margin" else "USD_million_rounded"
            if fact["unit"] != expected_unit:
                raise ValueError(f"WFC selected-fact unit differs: {fact['id']}")
            columns = reported_columns(ratios if expected_unit == "percent" else earnings,
                                       fact["source_row"])
            if Decimal(str(fact["value"])) != columns[0]:
                raise ValueError(f"WFC selected SEC row differs: {fact['id']}")
            selected[role][fact["metric"]] = columns[0]
            source_rows[role][fact["metric"]] = columns
    for metric, baseline_value in selected["baseline"].items():
        if source_rows["event"][metric][1] != baseline_value:
            raise ValueError(f"WFC Q2 cross-filing comparator differs: {metric}")
    bundle = derive(packet)
    deltas = {metric: row["delta_value"] for metric, row in bundle["rows"].items()}
    if deltas != EXPECTED_DELTAS:
        raise ValueError("WFC deterministic deltas differ from frozen oracle")
    revenue_mix = decompose_change(bundle, "gaap_total_revenue",
                                   ["gaap_net_interest_income", "gaap_noninterest_income"])
    if revenue_mix["unlisted_residual_usd_million"] != "0":
        raise ValueError("WFC revenue mix does not reconcile")
    return {"status": "selected_wfc_rows_units_comparators_and_deltas_match_locked_sec_sources",
            "selected_facts": 18, "cross_filing_comparator_checks": 9,
            "comparisons": deltas, "revenue_mix_residual_usd_million": "0",
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()),
                           json.loads(LOCK.read_text())), indent=2))
