#!/usr/bin/env python3
"""Audit MSCI standalone-quarter income statement, tax and EPS rows."""

from __future__ import annotations

import json
import re
from decimal import Decimal, ROUND_HALF_UP

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "msci_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\d[\d,]*(?:\.\d+)?")
EXPECTED = {
    "gaap_operating_revenues": (772679, 793426, "REV", "Operating revenues", "USD_thousand_reported"),
    "gaap_total_operating_expenses": (347445, 345736, "OPEX", "Total operating expenses(1)", "USD_thousand_reported"),
    "gaap_operating_income": (425234, 447690, "OPINC", "Operating income", "USD_thousand_reported"),
    "gaap_other_expense_net": (47394, 51182, "OTHEREXP", "Other expense (income), net", "USD_thousand_reported"),
    "gaap_income_before_taxes": (377840, 396508, "PRETAX", "Income before provision for income taxes", "USD_thousand_reported"),
    "gaap_provision_for_income_taxes": (74190, 71122, "TAX", "Provision for income taxes", "USD_thousand_reported"),
    "gaap_net_income": (303650, 325386, "NET", "Net income", "USD_thousand_reported"),
    "gaap_diluted_eps": (Decimal("3.92"), Decimal("4.25"), "EPS", "Earnings per diluted common share", "USD_per_share_reported"),
    "diluted_weighted_average_shares": (77496, 76579, "SHARES", "Diluted", "thousand_shares_reported"),
}


def _current_quarter_value(rows: list[list[str]], label: str, end: str) -> Decimal:
    headers = [i for i, row in enumerate(rows[:120])
               if row and row[0] == "In thousands, except per share data"
               and [cell for cell in row if cell in ("2025", "2024")][:4]
               == ["2025", "2024", "2025", "2024"]]
    if len(headers) != 1:
        raise ValueError("MSCI consolidated statement header missing/ambiguous")
    start = headers[0]
    if ("Three Months Ended" not in " ".join(rows[start - 2])
            or end not in " ".join(rows[start - 1])):
        raise ValueError("MSCI current standalone-quarter period differs")
    matches = [row for row in rows[start + 1:start + 25]
               if row and row[0] == label]
    if len(matches) != 1:
        raise ValueError(f"MSCI consolidated source row missing/ambiguous: {label}")
    values = [Decimal(cell.replace(",", "")) for cell in matches[0][1:]
              if NUMERIC.fullmatch(cell)]
    if len(values) != 4:
        raise ValueError(f"MSCI statement does not have four numeric columns: {label}")
    return values[0]  # The statement puts current standalone quarter first.


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "MSCI"
            or packet.get("cik") != "0001408198"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected MSCI packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, filed_at in (
        ("baseline", "HOLDOUT-MSCI-BASELINE-v1", "Q2", "June 30,", "2025-07-22"),
        ("event", "HOLDOUT-MSCI-EVENT-v1", "Q3", "Sep. 30,", "2025-10-28"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{'06-30' if quarter == 'Q2' else '09-30'}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"MSCI filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"MSCI selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, source_row, unit = EXPECTED[metric]
            expected = Decimal(str(q2 if quarter == "Q2" else q3))
            if (fact["id"] != f"MSCI-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != source_row
                    or fact["locator"] !=
                    f"Consolidated statement / Three Months Ended {'June 30,' if quarter == 'Q2' else 'September 30,'} 2025 current column"):
                raise ValueError(f"MSCI selected fact definition differs: {fact['id']}")
            actual = _current_quarter_value(rows, source_row, end)
            if actual != expected:
                raise ValueError(f"MSCI SEC standalone-quarter row differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    for role, values in selected.items():
        if (values["gaap_operating_revenues"] - values["gaap_total_operating_expenses"]
                != values["gaap_operating_income"]
                or values["gaap_operating_income"] - values["gaap_other_expense_net"]
                != values["gaap_income_before_taxes"]
                or values["gaap_income_before_taxes"] - values["gaap_provision_for_income_taxes"]
                != values["gaap_net_income"]):
            raise ValueError(f"MSCI income statement bridge differs: {role}")
        computed_eps = (values["gaap_net_income"] / values["diluted_weighted_average_shares"])
        if computed_eps.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) != values["gaap_diluted_eps"]:
            raise ValueError(f"MSCI diluted EPS/share rounding differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {key: after[key] - before[key] for key in EXPECTED}
    if delta != {
        "gaap_operating_revenues": 20747,
        "gaap_total_operating_expenses": -1709,
        "gaap_operating_income": 22456,
        "gaap_other_expense_net": 3788,
        "gaap_income_before_taxes": 18668,
        "gaap_provision_for_income_taxes": -3068,
        "gaap_net_income": 21736,
        "gaap_diluted_eps": Decimal("0.33"),
        "diluted_weighted_average_shares": -917,
    }:
        raise ValueError("MSCI selected Q3-minus-Q2 changes differ")
    return {"status": "msci_standalone_quarter_source_and_income_bridges_match",
            "selected_facts": 18, "revenue_delta_usd_thousand": 20747,
            "net_income_delta_usd_thousand": 21736,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
