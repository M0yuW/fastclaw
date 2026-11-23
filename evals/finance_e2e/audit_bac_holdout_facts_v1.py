#!/usr/bin/env python3
"""Audit BAC's GAAP quarter columns and accounting bridge in locked SEC exhibits."""

from __future__ import annotations

import hashlib
import json
import re

from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import build_bundle
from sec_exhibit_text import extract_lines


PACKET = ROOT / "bac_holdout_fact_packet_v1.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
ROWS = (
    "Net interest income", "Noninterest income",
    "Total revenue, net of interest expense", "Provision for credit losses",
    "Noninterest expense", "Income before income taxes", "Income tax expense",
    "Net income", "Preferred stock dividends",
    "Net income applicable to common shareholders",
)
EXPECTED_DELTAS = {
    "gaap_net_interest_income": 563,
    "gaap_noninterest_income": 1062,
    "gaap_total_revenue_net_of_interest_expense": 1625,
    "gaap_provision_for_credit_losses": -297,
    "gaap_noninterest_expense": 154,
    "gaap_income_before_income_taxes": 1768,
    "gaap_income_tax_expense": 415,
    "gaap_net_income": 1353,
    "gaap_preferred_stock_dividends": 138,
    "gaap_net_income_applicable_to_common": 1215,
}


def summary_income_statement(path, header):
    """Return the five reported columns from the sole summary-income table."""
    matching = [line for line in extract_lines(path)
                if "Selected Financial Data (In millions, except per share data)" in line
                and "Summary Income Statement" in line]
    if len(matching) != 1:
        raise ValueError("BAC summary income statement not unique")
    text = matching[0]
    if header not in text:
        raise ValueError("BAC quarter-column header differs")
    summary = text.split("Summary Income Statement", 1)[1].split(
        "Summary Average Balance Sheet", 1)[0]
    if not summary or "Summary Average Balance Sheet" not in text:
        raise ValueError("BAC summary income-statement boundary missing")
    result = {}
    five_amounts = r"".join(r"\s+\$?\s*([\d,]+)" for _ in range(5))
    for row in ROWS:
        pattern = re.compile(r"(?<!\w)" + re.escape(row) + five_amounts)
        found = list(pattern.finditer(summary))
        if len(found) != 1:
            raise ValueError(f"BAC row missing or ambiguous: {row}")
        result[row] = tuple(int(value.replace(",", ""))
                            for value in found[0].groups())
    return result


def bridge(values):
    if values["Net interest income"] + values["Noninterest income"] != values[
            "Total revenue, net of interest expense"]:
        raise ValueError("BAC revenue components do not reconcile")
    if (values["Total revenue, net of interest expense"]
            - values["Provision for credit losses"]
            - values["Noninterest expense"]
            != values["Income before income taxes"]):
        raise ValueError("BAC pretax income does not reconcile")
    if (values["Income before income taxes"] - values["Income tax expense"]
            != values["Net income"]):
        raise ValueError("BAC net income does not reconcile")
    if (values["Net income"] - values["Preferred stock dividends"]
            != values["Net income applicable to common shareholders"]):
        raise ValueError("BAC common net income does not reconcile")


def audit(packet: dict, lock: dict) -> dict:
    if (packet.get("version") != 1 or packet.get("symbol") != "BAC"
            or packet.get("cik") != "0000070858"):
        raise ValueError("unexpected BAC fact packet")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    selected = {}
    for period, source_id, header in (
        ("baseline", "HOLDOUT-BAC-BASELINE-v1",
         "Second Quarter 2025 First Quarter 2025 Second Quarter 2024"),
        ("event", "HOLDOUT-BAC-EVENT-v1",
         "Third Quarter 2025 Second Quarter 2025 Third Quarter 2024"),
    ):
        section, source = packet[period], entries[source_id]
        if (section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"BAC source differs from lock: {period}")
        path = ROOT / source["local_path"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError(f"BAC local source hash differs: {period}")
        rows = summary_income_statement(path, header)
        facts = section["facts"]
        if len(facts) != len(ROWS) or {fact["source_row"] for fact in facts} != set(ROWS):
            raise ValueError(f"BAC selected rows incomplete or duplicated: {period}")
        for fact in facts:
            if fact["unit"] != "USD_million_rounded":
                raise ValueError(f"BAC selected-fact unit differs: {fact['id']}")
            if fact["value"] != rows[fact["source_row"]][2]:
                raise ValueError(f"BAC selected SEC row differs: {fact['id']}")
        selected[period] = {fact["source_row"]: fact["value"] for fact in facts}
        bridge(selected[period])
        if period == "event":
            prior_quarter = {row: values[3] for row, values in rows.items()}
            if prior_quarter != selected["baseline"]:
                raise ValueError("BAC Q2 cross-filing comparator differs")
    comparisons = {item["metric"]: int(item["delta_usd_thousand"]) // 1000
                   for item in build_bundle(packet)["comparisons"]}
    if comparisons != EXPECTED_DELTAS:
        raise ValueError("BAC deterministic deltas differ from frozen oracle")
    bridge({row: selected["event"][row] - selected["baseline"][row]
            for row in ROWS})
    return {"status": "selected_bac_rows_bridge_and_deltas_match_locked_sec_sources",
            "selected_facts": 20, "cross_filing_comparator_checks": 10,
            "comparisons": comparisons, "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text(encoding="utf-8")),
                           json.loads(LOCK.read_text(encoding="utf-8"))), indent=2))
