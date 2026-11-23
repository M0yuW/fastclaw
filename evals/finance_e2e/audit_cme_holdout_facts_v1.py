#!/usr/bin/env python3
"""Audit CME's one-decimal GAAP table cells against locked SEC releases."""

from __future__ import annotations

import json
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_decimal_table import first_decimal_column
from sec_exhibit_text import extract_lines


PACKET = ROOT / "cme_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
START = "CME Group Inc. and SubsidiariesConsolidated Statements of Income"
END = "Reconciliation of "


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 1 or packet.get("symbol") != "CME" or
            packet.get("cik") != "0001156375"):
        raise ValueError("unexpected CME fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    for period, source_id, month in (
            ("baseline", "HOLDOUT-CME-BASELINE-v1", "June"),
            ("event", "HOLDOUT-CME-EVENT-v1", "September")):
        section, source = packet[period], entries[source_id]
        if (section["source_url"] != source["url"] or
                section["source_sha256"] != source["sha256"] or
                section["local_path"] != source["local_path"]):
            raise ValueError(f"fact packet source differs from lock: {period}")
        lines = extract_lines(ROOT / source["local_path"])
        for fact in section["facts"]:
            if fact["unit"] != "USD_million_rounded":
                raise ValueError(f"wrong selected-fact unit: {fact['id']}")
            actual = first_decimal_column(
                lines, start_anchor=START, end_anchor=END,
                row_label=fact["source_row"],
                header_fragments=("Quarter Ended", f"{month} 30", "2025 2024 2025 2024"),
                min_columns=4)
            expected = Decimal(str(fact["value"]))
            if expected.as_tuple().exponent != -1 or actual != expected:
                raise ValueError(f"selected SEC decimal row differs: {fact['id']}")
    comparisons = {item["metric"]: Decimal(item["delta_usd_thousand"]) / 1000
                   for item in build_bundle(packet)["comparisons"]}
    expected_deltas = {
        "gaap_clearing_and_transaction_fees": Decimal("-160.1"),
        "gaap_market_data_and_information_services": Decimal("4.4"),
        "gaap_total_revenues": Decimal("-154.4"),
        "gaap_total_expenses": Decimal("2.3"),
        "gaap_operating_income": Decimal("-156.7"),
        "gaap_net_income_attributable_to_common": Decimal("-115.6"),
    }
    if comparisons != expected_deltas:
        raise ValueError("decimal comparisons differ from frozen oracle")
    return {"status": "selected_cme_decimal_rows_and_deltas_match_locked_sec_sources",
            "selected_facts": 12,
            "comparisons_usd_million_displayed": {key: str(value)
                                                  for key, value in comparisons.items()},
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    print(json.dumps(audit(packet, lock), indent=2))
