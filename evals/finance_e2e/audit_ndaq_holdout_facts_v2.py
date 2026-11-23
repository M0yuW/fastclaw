#!/usr/bin/env python3
"""Audit Nasdaq gross/net revenue and operating bridge in locked SEC exhibits."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "ndaq_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\d[\d,]*")
EXPECTED = {
    "gaap_capital_access_gross_revenue": (527, 546, "CAP", "Capital Access Platforms"),
    "gaap_financial_technology_gross_revenue": (464, 457, "FINTECH", "Financial Technology"),
    "gaap_market_services_gross_revenue": (1090, 946, "MARKET", "Market Services"),
    "gaap_other_gross_revenue": (9, 9, "OTHER", "Other Revenues"),
    "gaap_total_gross_revenue": (2090, 1958, "GROSS", "Total revenues"),
    "gaap_revenue_less_transaction_expenses":
        (1306, 1315, "NETREV", "Revenues less transaction-based expenses"),
    "gaap_total_operating_expenses": (738, 729, "OPEX", "Total operating expenses"),
    "gaap_operating_income": (568, 586, "OPINC", "Operating income"),
    "gaap_net_income_attributable_to_nasdaq":
        (452, 423, "NETATTR", "Net income attributable to Nasdaq"),
}
SEGMENTS = ["gaap_capital_access_gross_revenue",
            "gaap_financial_technology_gross_revenue",
            "gaap_market_services_gross_revenue",
            "gaap_other_gross_revenue"]


def _current_quarter_value(rows: list[list[str]], label: str, end: str,
                           cumulative: str) -> int:
    headers = [i for i, row in enumerate(rows[:100])
               if "Three Months Ended" in " ".join(row)
               and f"{cumulative} Months Ended" in " ".join(row)]
    # The exhibit repeats the quarter header in later segment/reconciliation
    # tables. Its first occurrence is the consolidated GAAP statement.
    if not headers:
        raise ValueError("Nasdaq consolidated quarter header missing/ambiguous")
    start = headers[0]
    years = [cell for cell in rows[start + 1] if end in cell or "2024" in cell]
    if len(years) < 4 or end not in years[0] or "2024" not in years[1]:
        raise ValueError("Nasdaq standalone-quarter current-year column differs")
    matches = [row for row in rows[start + 2:start + 40]
               if row and row[0] == label]
    if len(matches) != 1:
        raise ValueError(f"Nasdaq source row missing/ambiguous: {label}")
    values = [int(cell.replace(",", "")) for cell in matches[0][1:]
              if NUMERIC.fullmatch(cell)]
    if len(values) < 4:
        raise ValueError(f"Nasdaq selected row has fewer than four columns: {label}")
    return values[0]


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "NDAQ"
            or packet.get("cik") != "0001120193"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected Nasdaq packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, cumulative, filed_at in (
        ("baseline", "HOLDOUT-NDAQ-BASELINE-v1", "Q2", "June 30,2025", "Six", "2025-07-24"),
        ("event", "HOLDOUT-NDAQ-EVENT-v1", "Q3", "September 30,2025", "Nine", "2025-10-21"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{'06-30' if quarter == 'Q2' else '09-30'}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"Nasdaq filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"Nasdaq selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, source_row = EXPECTED[metric]
            expected = q2 if quarter == "Q2" else q3
            locator = ("Consolidated statement / Three Months Ended "
                       f"{'June 30,' if quarter == 'Q2' else 'September 30,'} 2025 current column")
            if (fact["id"] != f"NDAQ-{quarter}-{suffix}"
                    or fact["value"] != expected
                    or fact["unit"] != "USD_million_rounded"
                    or fact["source_row"] != source_row or fact["locator"] != locator):
                raise ValueError(f"Nasdaq selected fact definition differs: {fact['id']}")
            actual = _current_quarter_value(rows, source_row, end, cumulative)
            if actual != expected:
                raise ValueError(f"Nasdaq SEC quarter row differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    for role, values in selected.items():
        if values["gaap_total_gross_revenue"] != sum(values[metric] for metric in SEGMENTS):
            raise ValueError(f"Nasdaq gross segment bridge differs: {role}")
        if (values["gaap_revenue_less_transaction_expenses"]
                - values["gaap_total_operating_expenses"] != values["gaap_operating_income"]):
            raise ValueError(f"Nasdaq operating-income bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    deltas = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if deltas != {
        "gaap_capital_access_gross_revenue": 19,
        "gaap_financial_technology_gross_revenue": -7,
        "gaap_market_services_gross_revenue": -144,
        "gaap_other_gross_revenue": 0,
        "gaap_total_gross_revenue": -132,
        "gaap_revenue_less_transaction_expenses": 9,
        "gaap_total_operating_expenses": -9,
        "gaap_operating_income": 18,
        "gaap_net_income_attributable_to_nasdaq": -29,
    }:
        raise ValueError("Nasdaq selected Q3-minus-Q2 changes differ")
    transaction_before = before["gaap_total_gross_revenue"] - before["gaap_revenue_less_transaction_expenses"]
    transaction_after = after["gaap_total_gross_revenue"] - after["gaap_revenue_less_transaction_expenses"]
    if (transaction_before, transaction_after) != (784, 643):
        raise ValueError("Nasdaq implied transaction-expense bridge differs")
    return {"status": "ndaq_selected_sec_rows_and_gross_net_bridges_match",
            "selected_facts": 18, "gross_delta_usd_million": -132,
            "net_delta_usd_million": 9,
            "implied_transaction_expense_delta_usd_million": -141,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
