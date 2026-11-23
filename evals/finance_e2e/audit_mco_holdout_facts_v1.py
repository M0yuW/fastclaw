#!/usr/bin/env python3
"""Audit selected Moody's fact cells and a segment counterpoint from SEC exhibits."""

from __future__ import annotations

import json

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines
from sec_inline_table import first_column_value


PACKET = ROOT / "mco_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
START = "Amounts in millions, except per share amounts"
END = "Table 2 - Condensed Consolidated Balance Sheet Data"


def audit(packet: dict, lock: dict) -> dict:
    if packet.get("version") != 1 or packet.get("symbol") != "MCO":
        raise ValueError("unexpected Moody's fact packet")
    entries = {item["id"]: item for item in lock["entries"]}
    for period, label, month in (("baseline", "HOLDOUT-MCO-BASELINE-v1", "June"),
                                 ("event", "HOLDOUT-MCO-EVENT-v1", "September")):
        section, source = packet[period], entries[label]
        if (section["source_url"] != source["url"] or
                section["source_sha256"] != source["sha256"] or
                section["local_path"] != source["local_path"]):
            raise ValueError(f"fact packet source differs from lock: {period}")
        lines = extract_lines(ROOT / source["local_path"])
        for fact in section["facts"]:
            if fact["unit"] != "USD_million_rounded":
                raise ValueError(f"wrong selected-fact unit: {fact['id']}")
            actual = first_column_value(lines, start_anchor=START, end_anchor=END,
                                        row_label=fact["source_row"],
                                        header_fragments=(f"Three Months Ended{month} 30", "2025"),
                                        min_columns=4)
            if actual != fact["value"]:
                raise ValueError(f"selected SEC row differs: {fact['id']}")
        if period == "event":
            if packet["qualitative_source_signal"]["anchor_phrase"].lower() not in " ".join(lines[:60]).lower():
                raise ValueError("Moody's Analytics counterevidence anchor missing")
    bundle = build_bundle(packet)
    observed = {item["metric"]: int(item["delta_usd_thousand"]) // 1000
                for item in bundle["comparisons"]}
    expected = {"gaap_revenue": 109, "gaap_total_expenses": 10,
                "gaap_operating_income": 99,
                "gaap_net_income_attributable_to_moodys": 68}
    if observed != expected:
        raise ValueError("deterministic comparisons differ from frozen oracle")
    return {"status": "selected_moodys_rows_and_deltas_match_locked_sec_sources",
            "selected_facts": 8, "comparisons": observed,
            "segment_counterevidence_attributed": True, "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, lock), indent=2))
