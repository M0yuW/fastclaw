#!/usr/bin/env python3
"""Audit ICE standalone-quarter columns in two locked SEC EX-99.1 exhibits."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "ice_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\d[\d,]*")
EXPECTED = {
    "gaap_exchanges_gross_revenue": (2134, 1861, "EXCH", "Exchanges"),
    "gaap_fixed_income_data_gross_revenue":
        (597, 618, "FIDS", "Fixed income and data services"),
    "gaap_mortgage_technology_gross_revenue":
        (531, 528, "MORT", "Mortgage technology"),
    "gaap_total_gross_revenue": (3262, 3007, "GROSS", "Total revenues"),
    "gaap_revenue_less_transaction_expenses":
        (2543, 2411, "NETREV", "Total revenues, less transaction-based expenses"),
    "gaap_total_operating_expenses":
        (1246, 1237, "OPEX", "Total operating expenses"),
    "gaap_operating_income": (1297, 1174, "OPINC", "Operating income"),
    "gaap_net_income_attributable_to_ice":
        (851, 816, "NETATTR", "Net income attributable to Intercontinental Exchange, Inc."),
}


def _current_quarter_value(rows: list[list[str]], row_label: str, end: str,
                           ytd_months: str) -> int:
    header_matches = [i for i, row in enumerate(rows[:120])
                      if " ".join(row).count(f"Three Months Ended {end}") == 1
                      and f"{ytd_months} Months Ended {end}" in " ".join(row)]
    if len(header_matches) != 1:
        raise ValueError(f"ICE standalone-quarter table header missing/ambiguous: {end}")
    start = header_matches[0]
    years = [int(cell) for cell in rows[start + 1] if cell in ("2025", "2024")]
    if years[:4] != [2025, 2024, 2025, 2024]:
        raise ValueError("ICE YTD versus standalone-quarter year header differs")
    matches = [row for row in rows[start + 2:start + 40]
               if row and row[0] == row_label]
    if len(matches) != 1:
        raise ValueError(f"ICE selected source row missing/ambiguous: {row_label}")
    values = [int(cell.replace(",", "")) for cell in matches[0][1:]
              if NUMERIC.fullmatch(cell)]
    if len(values) < 4:
        raise ValueError(f"ICE four financial statement columns missing: {row_label}")
    return values[2]  # 2025 single quarter, not the first (YTD) numeric column.


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "ICE"
            or packet.get("cik") != "0001571949"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected ICE packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, ytd_months, filed_at in (
        ("baseline", "HOLDOUT-ICE-BASELINE-v1", "Q2", "June 30,", "Six", "2025-07-31"),
        ("event", "HOLDOUT-ICE-EVENT-v1", "Q3", "September 30,", "Nine", "2025-10-30"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{'06-30' if quarter == 'Q2' else '09-30'}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"ICE filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"ICE selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, source_row = EXPECTED[metric]
            expected = q2 if quarter == "Q2" else q3
            if (fact["id"] != f"ICE-{quarter}-{suffix}"
                    or fact["value"] != expected
                    or fact["unit"] != "USD_million_rounded"
                    or fact["source_row"] != source_row
                    or f"Three Months Ended {end} 2025; third numeric column"
                    != fact["locator"]):
                raise ValueError(f"ICE selected fact definition differs: {fact['id']}")
            actual = _current_quarter_value(rows, source_row, end, ytd_months)
            if actual != expected:
                raise ValueError(f"ICE SEC standalone-quarter row differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    for role, values in selected.items():
        if values["gaap_total_gross_revenue"] != sum(values[metric] for metric in (
                "gaap_exchanges_gross_revenue", "gaap_fixed_income_data_gross_revenue",
                "gaap_mortgage_technology_gross_revenue")):
            raise ValueError(f"ICE gross segment revenue bridge differs: {role}")
        if (values["gaap_revenue_less_transaction_expenses"]
                - values["gaap_total_operating_expenses"]
                != values["gaap_operating_income"]):
            raise ValueError(f"ICE operating income bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_exchanges_gross_revenue": -273,
        "gaap_fixed_income_data_gross_revenue": 21,
        "gaap_mortgage_technology_gross_revenue": -3,
        "gaap_total_gross_revenue": -255,
        "gaap_revenue_less_transaction_expenses": -132,
        "gaap_total_operating_expenses": -9,
        "gaap_operating_income": -123,
        "gaap_net_income_attributable_to_ice": -35,
    }:
        raise ValueError("ICE selected Q3-minus-Q2 changes differ")
    if ((before["gaap_total_gross_revenue"] - before["gaap_revenue_less_transaction_expenses"])
            - (after["gaap_total_gross_revenue"] - after["gaap_revenue_less_transaction_expenses"])
            != 123):
        raise ValueError("ICE implied transaction-expense change differs")
    return {"status": "ice_standalone_quarter_source_rows_and_bridges_match",
            "selected_facts": 16, "gross_revenue_delta_usd_million": -255,
            "net_revenue_delta_usd_million": -132, "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
