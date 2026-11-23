#!/usr/bin/env python3
"""Audit Fiserv's selected GAAP/non-GAAP rows against locked SEC exhibits."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines
from sec_inline_table import first_column_value


PACKET = ROOT / "fisv_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"


def current_value(lines: list[str], fact: dict) -> int:
    next_section = ("Reconciliation of GAAP to" if "Consolidated" in fact["section_anchor"]
                    else "Financial Results by Segment")
    expected = re.fullmatch(r"Three Months Ended (June|September) 30, 2025", fact["source_column"])
    if not expected:
        raise ValueError(f"current-quarter column mismatch: {fact['id']}")
    return first_column_value(
        lines, start_anchor=fact["section_anchor"], end_anchor=next_section,
        row_label=fact["source_row"],
        header_fragments=(f"Three Months Ended {expected.group(1)} 30", "2025"),
        min_columns=4)


def audit(packet: dict, lock: dict) -> dict:
    if packet.get("version") != 1 or packet.get("symbol") != "FISV":
        raise ValueError("unexpected Fiserv fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    for period, source_id in (("baseline", "HOLDOUT-FISV-BASELINE-v1"),
                              ("event", "HOLDOUT-FISV-EVENT-v1")):
        section, entry = packet[period], entries[source_id]
        if (section["source_sha256"] != entry["sha256"] or
                section["source_url"] != entry["url"] or
                section["local_path"] != entry["local_path"]):
            raise ValueError(f"fact packet source differs from lock: {period}")
        lines = extract_lines(ROOT / entry["local_path"])
        for fact in section["facts"]:
            if fact["unit"] != "USD_million_rounded" or current_value(lines, fact) != fact["value"]:
                raise ValueError(f"selected SEC row differs: {fact['id']}")
        if period == "event":
            source_text = " ".join(lines[:25]).lower()
            for phrase in packet["qualitative_source_signal"]["anchor_phrases"]:
                if phrase.lower() not in source_text:
                    raise ValueError(f"management-statement anchor missing: {phrase}")
    bundle = build_bundle(packet)
    expected_deltas = {"gaap_total_revenue": -253, "gaap_operating_income": -260,
                       "gaap_net_income_attributable_to_fiserv": -234,
                       "adjusted_net_income_non_gaap": -259}
    observed = {item["metric"]: int(item["delta_usd_thousand"]) // 1000
                for item in bundle["comparisons"]}
    if observed != expected_deltas:
        raise ValueError("deterministic comparisons differ from frozen oracle")
    return {"status": "selected_fiserv_rows_and_deltas_match_locked_sec_sources",
            "selected_facts": 8, "comparisons": observed,
            "management_signal_attributed_not_causal_proof": True,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, lock), indent=2))
