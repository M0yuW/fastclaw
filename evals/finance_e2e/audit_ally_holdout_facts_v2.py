#!/usr/bin/env python3
"""Audit selected Ally Q2/Q3 GAAP rows and the cross-filing comparator."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "ally_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
NUMERIC = re.compile(r"\d[\d,]*(?:\.\d+)?")
EXPECTED = {
    "gaap_total_net_revenue": (2082, 2168, "USD_million_rounded"),
    "gaap_net_financing_revenue": (1516, 1584, "USD_million_rounded"),
    "gaap_other_revenue": (566, 584, "USD_million_rounded"),
    "gaap_provision_for_credit_losses": (384, 415, "USD_million_rounded"),
    "gaap_noninterest_expense": (1262, 1240, "USD_million_rounded"),
    "gaap_pre_tax_income": (436, 513, "USD_million_rounded"),
    "gaap_net_income_attributable_to_common": (324, 371, "USD_million_rounded"),
    "gaap_eps": (Decimal("1.04"), Decimal("1.18"), "USD_per_share_reported"),
}
SUFFIX = {
    "gaap_total_net_revenue": "REV",
    "gaap_net_financing_revenue": "NFR",
    "gaap_other_revenue": "OTHER",
    "gaap_provision_for_credit_losses": "PROV",
    "gaap_noninterest_expense": "OPEX",
    "gaap_pre_tax_income": "PRETAX",
    "gaap_net_income_attributable_to_common": "NETCOMMON",
    "gaap_eps": "EPS",
}
SOURCE_ROW = {
    "gaap_total_net_revenue": "GAAP Total Net Revenue",
    "gaap_net_financing_revenue": "(a) Net Financing Revenue",
    "gaap_other_revenue": "(b) Other Revenue",
    "gaap_provision_for_credit_losses": "(c) Provision for Credit Losses",
    "gaap_noninterest_expense": "(d) Noninterest Expense",
    "gaap_pre_tax_income": "Pre-Tax Income (loss) (a+b-c-d)",
    "gaap_net_income_attributable_to_common":
        "GAAP Net Income (Loss) Attributable to Common Shareholders",
    "gaap_eps": "GAAP Earnings per Common Share (basic or diluted as applicable)",
}


def _first_three_cells(rows: list[list[str]], label: str, current: str, prior: str) -> list[Decimal]:
    # Both exhibits repeat common-income rows in a later reconciliation table.
    # Only the two opening "Financial Results" tables belong to this packet.
    candidates = [(i, row) for i, row in enumerate(rows[:50]) if row and row[0] == label]
    if len(candidates) != 1:
        raise ValueError(f"selected source row missing or ambiguous: {label}")
    i, row = candidates[0]
    headers = [" ".join(item) for item in rows[max(0, i - 20):i]
               if any("millions except per share data" in cell for cell in item)]
    if not headers or current not in headers[-1] or prior not in headers[-1]:
        raise ValueError(f"quarter header mismatch: {label}")
    cells = [Decimal(cell.replace(",", "")) for cell in row[1:]
             if NUMERIC.fullmatch(cell)]
    if len(cells) < 3:
        raise ValueError(f"too few numeric source columns: {label}")
    return cells[:3]


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "ALLY"
            or packet.get("cik") != "0000040729"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected Ally packet identity")
    entries = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected: dict[str, dict[str, Decimal]] = {}
    event_prior: dict[str, Decimal] = {}
    for section_name, source_id, current, prior, period, filed_at in (
        ("baseline", "HOLDOUT-V2-ALLY-BASELINE", "2Q 25", "1Q 25",
         "CY2025 Q2 ended 2025-06-30", "2025-07-18"),
        ("event", "HOLDOUT-V2-ALLY-EVENT", "3Q 25", "2Q 25",
         "CY2025 Q3 ended 2025-09-30", "2025-10-17"),
    ):
        section, source, discovery = packet[section_name], entries[source_id], discoveries[source_id]
        if (section["period"] != period or section["as_of"] != filed_at
                or discovery["filed_at"] != filed_at
                or discovery["document_type"] != "EX-99.1"
                or discovery["form"] != "8-K"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"Ally source/filing identity differs: {section_name}")
        rows = extract_rows(ROOT / source["local_path"])
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"selected metric set differs: {section_name}")
        values: dict[str, Decimal] = {}
        for fact in facts:
            metric = fact["metric"]
            expected = EXPECTED[metric][0 if section_name == "baseline" else 1]
            quarter = "Q2" if section_name == "baseline" else "Q3"
            if (fact["unit"] != EXPECTED[metric][2]
                    or Decimal(str(fact["value"])) != Decimal(str(expected))
                    or fact["id"] != f"ALLY-{quarter}-{SUFFIX[metric]}"
                    or fact["source_row"] != SOURCE_ROW[metric]):
                raise ValueError(f"selected fact definition differs: {fact['id']}")
            cells = _first_three_cells(rows, fact["source_row"], current, prior)
            if cells[0] != Decimal(str(fact["value"])):
                raise ValueError(f"selected SEC row differs: {fact['id']}")
            values[metric] = cells[0]
            if section_name == "event":
                event_prior[metric] = cells[1]
        selected[section_name] = values
    if event_prior != selected["baseline"]:
        raise ValueError("Q3 exhibit Q2 comparator differs from Q2 release")
    for quarter, values in selected.items():
        if values["gaap_total_net_revenue"] != (values["gaap_net_financing_revenue"]
                                                 + values["gaap_other_revenue"]):
            raise ValueError(f"Ally revenue bridge differs: {quarter}")
        if values["gaap_pre_tax_income"] != (values["gaap_total_net_revenue"]
                                               - values["gaap_provision_for_credit_losses"]
                                               - values["gaap_noninterest_expense"]):
            raise ValueError(f"Ally pre-tax bridge differs: {quarter}")
    delta = {metric: selected["event"][metric] - selected["baseline"][metric]
             for metric in EXPECTED}
    if (delta["gaap_total_net_revenue"] != 86
            or delta["gaap_net_financing_revenue"] != 68
            or delta["gaap_other_revenue"] != 18
            or delta["gaap_provision_for_credit_losses"] != 31
            or delta["gaap_noninterest_expense"] != -22
            or delta["gaap_pre_tax_income"] != 77
            or delta["gaap_net_income_attributable_to_common"] != 47
            or delta["gaap_eps"] != Decimal("0.14")):
        raise ValueError("Ally Q3-Q2 selected deltas differ")
    return {"status": "ally_selected_rows_cross_filing_comparators_and_bridges_match",
            "selected_facts": 16, "q2_cross_filing_comparators": 8,
            "revenue_delta_usd_million": 86, "pretax_delta_usd_million": 77,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
