#!/usr/bin/env python3
"""Audit BNY's selected quarter facts against two locked SEC earnings exhibits."""

from __future__ import annotations

import json

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines
from sec_inline_table import first_column_value


PACKET = ROOT / "bny_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
START = "KEY FINANCIAL INFORMATION"
END = "Selected metrics:"


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 1 or packet.get("symbol") != "BNY" or
            packet.get("cik") != "0001390777"):
        raise ValueError("unexpected BNY fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    for period, source_id, period_header in (
            ("baseline", "HOLDOUT-BNY-BASELINE-v1", "2Q25 1Q25 2Q24"),
            ("event", "HOLDOUT-BNY-EVENT-v1", "3Q25 2Q25 3Q24")):
        section, source = packet[period], entries[source_id]
        if (section["source_url"] != source["url"] or
                section["source_sha256"] != source["sha256"] or
                section["local_path"] != source["local_path"]):
            raise ValueError(f"fact packet source differs from lock: {period}")
        lines = extract_lines(ROOT / source["local_path"])
        for fact in section["facts"]:
            if fact["unit"] != "USD_million_rounded":
                raise ValueError(f"wrong selected-fact unit: {fact['id']}")
            actual = first_column_value(
                lines, start_anchor=START, end_anchor=END,
                row_label=fact["source_row"],
                header_fragments=(period_header, "dollars in millions"),
                min_columns=2)
            if actual != fact["value"]:
                raise ValueError(f"selected SEC row differs: {fact['id']}")
    comparisons = {item["metric"]: int(item["delta_usd_thousand"]) // 1000
                   for item in build_bundle(packet)["comparisons"]}
    expected = {"gaap_fee_revenue": -4, "gaap_net_interest_income": 33,
                "gaap_total_revenue": 53, "gaap_noninterest_expense": 30,
                "gaap_net_income_applicable_to_common": -52}
    if comparisons != expected:
        raise ValueError("deterministic comparisons differ from frozen oracle")
    return {"status": "selected_bny_rows_and_deltas_match_locked_sec_sources",
            "selected_facts": 10, "comparisons": comparisons,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, lock), indent=2))
