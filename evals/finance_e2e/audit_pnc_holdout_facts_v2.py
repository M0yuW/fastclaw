#!/usr/bin/env python3
"""Audit PNC's quarterly current columns and Q2 cross-filing comparators."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines
from selected_fact_delta_guard_v1 import decompose_change, derive


PACKET = ROOT / "pnc_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
EXPECTED_UNITS = {
    "gaap_net_interest_income": "USD_million_rounded",
    "gaap_noninterest_income": "USD_million_rounded",
    "gaap_revenue": "USD_million_rounded",
    "gaap_noninterest_expense": "USD_million_rounded",
    "gaap_provision_for_credit_losses": "USD_million_rounded",
    "gaap_net_income": "USD_million_rounded",
    "reported_net_loan_charge_offs": "USD_million_rounded",
    "gaap_diluted_eps": "USD_per_share_reported",
    "non_gaap_net_interest_margin": "percent",
    "reported_cet1_capital_ratio": "percent",
}
EXPECTED_DELTAS = {
    "gaap_net_interest_income": "93",
    "gaap_noninterest_income": "161",
    "gaap_revenue": "254",
    "gaap_noninterest_expense": "78",
    "gaap_provision_for_credit_losses": "-87",
    "gaap_net_income": "179",
    "reported_net_loan_charge_offs": "-19",
    "gaap_diluted_eps": "0.5",
    "non_gaap_net_interest_margin": "-0.01",
    "reported_cet1_capital_ratio": "0.1",
}


def selected_columns(path, header: str, row_label: str) -> tuple[Decimal, Decimal, Decimal]:
    lines = extract_lines(path)
    if not any(line.startswith("In millions, except per share data and as noted ")
               and header in line for line in lines[:12]):
        raise ValueError("PNC reported quarter-column header differs")
    pattern = re.compile(r"^" + re.escape(row_label) + r"\s+\$?\s*\(?-?\d")
    matches = [line for line in lines[:40] if pattern.match(line)]
    if len(matches) != 1:
        raise ValueError(f"PNC selected row missing or ambiguous: {row_label}")
    values = re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?",
                        matches[0][len(row_label):])
    if len(values) != 3:
        raise ValueError(f"PNC three quarter columns missing: {row_label}")
    return tuple(Decimal(value.replace(",", "").strip("()"))
                 * (-1 if value.startswith("(") else 1) for value in values)


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 2 or packet.get("symbol") != "PNC"
            or packet.get("cik") != "0000713676"):
        raise ValueError("unexpected PNC fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    columns = {}
    for role, source_id, header in (
        ("baseline", "HOLDOUT-V2-PNC-BASELINE", "2Q25 1Q25 2Q24"),
        ("event", "HOLDOUT-V2-PNC-EVENT", "3Q25 2Q25 3Q24"),
    ):
        section, source = packet[role], entries[source_id]
        if any(section[field] != source[other] for field, other in (
                ("source_url", "url"), ("source_sha256", "sha256"),
                ("local_path", "local_path"))):
            raise ValueError(f"PNC source differs from lock: {role}")
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"PNC local source hash differs: {role}")
        facts = section["facts"]
        if len(facts) != 10 or len({fact["metric"] for fact in facts}) != 10:
            raise ValueError(f"PNC selected metric set differs: {role}")
        columns[role] = {}
        for fact in facts:
            metric = fact["metric"]
            if metric not in EXPECTED_UNITS or fact["unit"] != EXPECTED_UNITS[metric]:
                raise ValueError(f"PNC unit differs: {fact['id']}")
            selected = selected_columns(path, header, fact["source_row"])
            if Decimal(str(fact["value"])) != selected[0]:
                raise ValueError(f"PNC selected SEC row differs: {fact['id']}")
            columns[role][metric] = selected
    for metric, baseline_columns in columns["baseline"].items():
        if columns["event"][metric][1] != baseline_columns[0]:
            raise ValueError(f"PNC Q2 cross-filing comparator differs: {metric}")
    bundle = derive(packet)
    deltas = {metric: row["delta_value"] for metric, row in bundle["rows"].items()}
    if deltas != EXPECTED_DELTAS:
        raise ValueError("PNC deterministic deltas differ from frozen oracle")
    mix = decompose_change(bundle, "gaap_revenue",
                           ["gaap_net_interest_income", "gaap_noninterest_income"])
    if mix["unlisted_residual_usd_million"] != "0":
        raise ValueError("PNC revenue bridge differs")
    return {"status": "selected_pnc_rows_units_comparators_and_deltas_match_locked_sec_sources",
            "selected_facts": 20, "cross_filing_comparator_checks": 10,
            "comparisons": deltas, "revenue_mix_residual_usd_million": "0",
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()),
                           json.loads(LOCK.read_text())), indent=2))
