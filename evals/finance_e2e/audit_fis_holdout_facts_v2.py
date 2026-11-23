#!/usr/bin/env python3
"""Audit FIS GAAP loss-to-profit bridge and separate adjusted-earnings line."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "fis_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
EXPECTED = {
    "gaap_banking_solutions_revenue": (1808, 1894, "BANK", "Banking Solutions Revenue", "summary"),
    "gaap_capital_market_solutions_revenue": (765, 783, "CAP", "Capital Market Solutions Revenue", "summary"),
    "gaap_corporate_other_revenue": (43, 40, "CORP", "Corporate and Other Revenue", "summary"),
    "gaap_consolidated_revenue": (2616, 2717, "REV", "Consolidated FIS Revenue", "summary"),
    "gaap_operating_income": (408, 457, "OPINC", "Operating income", "statement"),
    "gaap_earnings_before_taxes_and_equity":
        (139, 375, "PRETAX", "Earnings (loss) before income taxes and equity method investment earnings (loss)", "statement"),
    "gaap_provision_for_income_taxes": (10, 87, "TAX", "Provision (benefit) for income taxes", "statement"),
    "gaap_equity_method_investment_earnings_net_of_tax":
        (-598, -23, "EQUITY", "Equity method investment earnings (loss), net of tax", "statement"),
    "gaap_net_earnings_continuing_operations":
        (-469, 265, "CONT", "Net earnings (loss) from continuing operations", "statement"),
    "gaap_net_earnings_attributable_to_fis":
        (-470, 264, "NETATTR", "Net earnings (loss) attributable to FIS", "statement"),
    "non_gaap_adjusted_net_earnings":
        (716, 789, "ADJNET", "Adjusted Net Earnings", "summary"),
}
REVENUE_COMPONENTS = ("gaap_banking_solutions_revenue",
                      "gaap_capital_market_solutions_revenue",
                      "gaap_corporate_other_revenue")


def _signed(cell: str) -> int:
    if not NUMERIC.fullmatch(cell):
        raise ValueError(f"not an FIS signed source cell: {cell}")
    value = cell.replace(",", "")
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    return int(value)


def _current_cell(rows: list[list[str]], label: str, section: str, quarter_end: str) -> int:
    if len(rows) < 47:
        raise ValueError("FIS source tables incomplete")
    if section == "summary":
        if ("Three Months Ended " + quarter_end) not in " ".join(rows[0]):
            raise ValueError("FIS continuing-operations summary quarter differs")
        candidates = rows[3:14]
    else:
        if ("Three months ended " + quarter_end) not in " ".join(rows[22]):
            raise ValueError("FIS consolidated statement quarter differs")
        if rows[23][1] != "2025":
            raise ValueError("FIS consolidated statement current-year column differs")
        candidates = rows[24:47]
    matches = [row for row in candidates if row and row[0] == label]
    if len(matches) != 1:
        raise ValueError(f"FIS source row missing/ambiguous: {label}")
    cells = [_signed(cell) for cell in matches[0][1:] if NUMERIC.fullmatch(cell)]
    if len(cells) < 2:
        raise ValueError(f"FIS row has fewer than two source columns: {label}")
    return cells[0]


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "FIS"
            or packet.get("cik") != "0001136893"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected FIS packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, filed_at in (
        ("baseline", "HOLDOUT-FIS-BASELINE-v1", "Q2", "June 30,", "2025-08-05"),
        ("event", "HOLDOUT-FIS-EVENT-v1", "Q3", "September 30,", "2025-11-05"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{'06-30' if quarter == 'Q2' else '09-30'}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"FIS filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"FIS selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, source_row, source_section = EXPECTED[metric]
            expected = q2 if quarter == "Q2" else q3
            locator = ("Continuing Operations summary / 2025 current column"
                       if source_section == "summary" else
                       f"Consolidated statements / Three months ended {end} 2025 current column")
            if (fact["id"] != f"FIS-{quarter}-{suffix}"
                    or fact["value"] != expected
                    or fact["unit"] != "USD_million_rounded"
                    or fact["source_row"] != source_row or fact["locator"] != locator):
                raise ValueError(f"FIS selected fact definition differs: {fact['id']}")
            actual = _current_cell(rows, source_row, source_section, end)
            if actual != expected:
                raise ValueError(f"FIS SEC current-quarter row differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    for role, values in selected.items():
        if values["gaap_consolidated_revenue"] != sum(values[metric] for metric in REVENUE_COMPONENTS):
            raise ValueError(f"FIS segment/corporate revenue bridge differs: {role}")
        if (values["gaap_earnings_before_taxes_and_equity"]
                - values["gaap_provision_for_income_taxes"]
                + values["gaap_equity_method_investment_earnings_net_of_tax"]
                != values["gaap_net_earnings_continuing_operations"]):
            raise ValueError(f"FIS continuing-operations income bridge differs: {role}")
        if values["gaap_net_earnings_attributable_to_fis"] != values["gaap_net_earnings_continuing_operations"] - 1:
            raise ValueError(f"FIS attributable-income/noncontrolling bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_banking_solutions_revenue": 86,
        "gaap_capital_market_solutions_revenue": 18,
        "gaap_corporate_other_revenue": -3,
        "gaap_consolidated_revenue": 101,
        "gaap_operating_income": 49,
        "gaap_earnings_before_taxes_and_equity": 236,
        "gaap_provision_for_income_taxes": 77,
        "gaap_equity_method_investment_earnings_net_of_tax": 575,
        "gaap_net_earnings_continuing_operations": 734,
        "gaap_net_earnings_attributable_to_fis": 734,
        "non_gaap_adjusted_net_earnings": 73,
    }:
        raise ValueError("FIS selected Q3-minus-Q2 changes differ")
    return {"status": "fis_signed_gaap_equity_loss_and_adjusted_separation_match",
            "selected_facts": 22, "gaap_attributable_delta_usd_million": 734,
            "equity_method_delta_usd_million": 575,
            "non_gaap_adjusted_delta_usd_million": 73,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
