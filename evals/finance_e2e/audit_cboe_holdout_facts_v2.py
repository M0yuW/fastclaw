#!/usr/bin/env python3
"""Audit CBOE as-reported and segment rows against locked Q2/Q3 SEC exhibits."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, ROUND_HALF_UP

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines
from selected_fact_delta_guard_v1 import decompose_change, derive


PACKET = ROOT / "cboe_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
SEGMENTS = ["reported_options_net_revenue",
            "reported_north_american_equities_net_revenue",
            "reported_europe_asia_pacific_net_revenue",
            "reported_futures_net_revenue", "reported_global_fx_net_revenue"]
EXPECTED_DELTAS = {
    "gaap_net_revenue": "18.2",
    "gaap_total_operating_expenses": "-13",
    "gaap_operating_income": "31.2",
    "gaap_reported_operating_margin": "3.5",
    "gaap_net_income_allocated_to_common": "65.4",
    "gaap_diluted_eps": "0.62",
    "reported_options_net_revenue": "16",
    "reported_north_american_equities_net_revenue": "5.1",
    "reported_europe_asia_pacific_net_revenue": "-1.3",
    "reported_futures_net_revenue": "-0.5",
    "reported_global_fx_net_revenue": "-1.1",
}


def table_sections(path, quarter: str) -> dict[str, list[str]]:
    lines = extract_lines(path)
    table1 = [i for i, line in enumerate(lines[:30]) if line == "Table 1"]
    table2 = [i for i, line in enumerate(lines[:35]) if line == "Table 2"]
    if len(table1) != 1 or len(table2) != 1 or table2[0] <= table1[0]:
        raise ValueError("CBOE summary tables missing or out of order")
    first = lines[table1[0] + 1:table2[0]]
    second = lines[table2[0] + 1:table2[0] + 11]
    if (not first or f"{quarter}25 {quarter}24 Change {quarter}25Adjusted" not in first[0]
            or not second or f"{quarter}25 {quarter}24 Change" not in second[0]):
        raise ValueError("CBOE current-year as-reported table headers differ")
    return {"Table 1": first[1:], "Table 2": second[1:]}


def first_current_value(lines: list[str], label: str) -> Decimal:
    pattern = re.compile(r"^" + re.escape(label) + r"\s+\$?\s*\(?-?\d")
    matches = [line for line in lines if pattern.match(line)]
    if len(matches) != 1:
        raise ValueError(f"CBOE selected row missing or ambiguous: {label}")
    token = re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", matches[0][len(label):])
    if not token:
        raise ValueError(f"CBOE reported value missing: {label}")
    raw = token.group()
    return Decimal(raw.replace(",", "").strip("()")) * (-1 if raw.startswith("(") else 1)


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 2 or packet.get("symbol") != "CBOE"
            or packet.get("cik") != "0001374310"):
        raise ValueError("unexpected CBOE fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    selected = {}
    for role, source_id, quarter in (
        ("baseline", "HOLDOUT-V2-CBOE-BASELINE", "2Q"),
        ("event", "HOLDOUT-V2-CBOE-EVENT", "3Q"),
    ):
        section, source = packet[role], entries[source_id]
        if any(section[field] != source[other] for field, other in (
                ("source_url", "url"), ("source_sha256", "sha256"),
                ("local_path", "local_path"))):
            raise ValueError(f"CBOE source differs from lock: {role}")
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"CBOE local source hash differs: {role}")
        tables = table_sections(path, quarter)
        facts = section["facts"]
        if len(facts) != 11 or len({fact["metric"] for fact in facts}) != 11:
            raise ValueError(f"CBOE selected metric set differs: {role}")
        selected[role] = {}
        for fact in facts:
            metric = fact["metric"]
            expected_unit = ("percent" if metric == "gaap_reported_operating_margin"
                             else "USD_per_share_reported" if metric == "gaap_diluted_eps"
                             else "USD_million_rounded")
            if fact["unit"] != expected_unit:
                raise ValueError(f"CBOE unit differs: {fact['id']}")
            table = "Table 2" if metric in SEGMENTS else "Table 1"
            if not fact["locator"].startswith(table):
                raise ValueError(f"CBOE source table differs: {fact['id']}")
            current = first_current_value(tables[table], fact["source_row"])
            if Decimal(str(fact["value"])) != current:
                raise ValueError(f"CBOE selected SEC row differs: {fact['id']}")
            selected[role][metric] = current
        values = selected[role]
        if sum((values[metric] for metric in SEGMENTS), Decimal(0)) != values["gaap_net_revenue"]:
            raise ValueError("CBOE segment net revenue does not reconcile")
        if values["gaap_net_revenue"] - values["gaap_total_operating_expenses"] != values["gaap_operating_income"]:
            raise ValueError("CBOE operating-income identity differs")
        margin = (values["gaap_operating_income"] / values["gaap_net_revenue"] * 100).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP)
        if margin != values["gaap_reported_operating_margin"]:
            raise ValueError("CBOE reported operating margin does not round from GAAP rows")
    bundle = derive(packet)
    deltas = {metric: row["delta_value"] for metric, row in bundle["rows"].items()}
    if deltas != EXPECTED_DELTAS:
        raise ValueError("CBOE deterministic deltas differ from frozen oracle")
    mix = decompose_change(bundle, "gaap_net_revenue", SEGMENTS)
    if mix["unlisted_residual_usd_million"] != "0":
        raise ValueError("CBOE segment-change revenue bridge differs")
    return {"status": "selected_cboe_as_reported_and_segment_rows_match_locked_sec_sources",
            "selected_facts": 22, "reconciled_quarters": 2,
            "comparisons": deltas, "segment_mix_residual_usd_million": "0",
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()),
                           json.loads(LOCK.read_text())), indent=2))
