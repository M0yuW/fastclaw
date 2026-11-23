#!/usr/bin/env python3
"""Audit WU standalone-quarter GAAP bridge, excluding full-year outlook cells."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "wu_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)")
EXPECTED = {
    "gaap_revenues": ("REV", (1026.1, 1032.6), "USD_million_rounded", "Revenues", "statement"),
    "gaap_cost_of_services": ("COST", (642.8, 643.2), "USD_million_rounded", "Cost of services", "statement"),
    "gaap_selling_general_administrative":
        ("SGA", (190.6, 187.5), "USD_million_rounded", "Selling, general, and administrative", "statement"),
    "gaap_total_expenses": ("EXP", (833.4, 830.7), "USD_million_rounded", "Total expenses", "statement"),
    "gaap_operating_income": ("OPINC", (192.7, 201.9), "USD_million_rounded", "Operating income", "statement"),
    "gaap_total_other_expense_net_signed":
        ("OTHER", (-33.0, -34.3), "USD_million_rounded", "Total other expense, net", "statement"),
    "gaap_income_before_income_taxes":
        ("PRETAX", (159.7, 167.6), "USD_million_rounded", "Income before income taxes", "statement"),
    "gaap_provision_for_income_taxes":
        ("TAX", (37.6, 28.0), "USD_million_rounded",
         ("Provision for income taxes", "Provision for/(benefit from) income taxes"), "statement"),
    "gaap_net_income": ("NET", (122.1, 139.6), "USD_million_rounded", "Net income", "statement"),
    "gaap_diluted_eps": ("EPS", (0.37, 0.43), "USD_per_share_reported", "Diluted", "eps"),
    "gaap_weighted_average_diluted_shares":
        ("SHARES", (329.6, 322.8), "million_shares_reported", "Diluted", "shares"),
}


def _number(cell: str) -> Decimal:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not a WU signed financial cell: {cell!r}")
    value = cell.replace(",", "")
    if value.startswith("("):
        value = "-" + value[1:-1]
    return Decimal(value)


def _current_cell(rows: list[list[str]], row_label: str, section: str, end: str) -> Decimal:
    if (len(rows) < 29 or rows[1][1] != "2025 Outlook"
            or rows[6][2] != "Three Months Ended" or rows[7][2] != end
            or rows[8][2] != "2025"):
        raise ValueError("WU actual-quarter table header differs")
    bounds = {"statement": (9, 23), "eps": (23, 26), "shares": (26, 29)}
    start, stop = bounds[section]
    matches = [row for row in rows[start:stop] if row and row[0] == row_label]
    if len(matches) != 1:
        raise ValueError(f"WU GAAP actual source row missing/ambiguous: {row_label} {section}")
    cells = [cell for cell in matches[0][1:] if NUMBER.fullmatch(cell)]
    if len(cells) < 2:
        raise ValueError(f"WU actual row lacks comparison column: {row_label}")
    return _number(cells[0])


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "WU"
            or packet.get("cik") != "0001365135"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected WU packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, period_end, filed_at in (
        ("baseline", "HOLDOUT-WU-BASELINE-v1", "Q2", "June 30,", "06-30", "2025-07-28"),
        ("event", "HOLDOUT-WU-EVENT-v1", "Q3", "September 30,", "09-30", "2025-10-23"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{period_end}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"WU filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"WU selected metric set differs: {role}")
        source_path = ROOT / source["local_path"]
        if "(in millions, except per share amounts)" not in source_path.read_text(
                encoding="utf-8", errors="replace").lower():
            raise ValueError(f"WU source unit declaration differs: {role}")
        rows = extract_rows(source_path)
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, labels, kind = EXPECTED[metric]
            expected = Decimal(str(pair[0 if quarter == "Q2" else 1]))
            row_label = labels[0 if quarter == "Q2" else 1] if isinstance(labels, tuple) else labels
            section_name = {"statement": "Statement", "eps": "Statement EPS",
                            "shares": "Statement weighted-average shares"}[kind]
            locator = f"{section_name} / Three Months Ended {end} 2025 actual"
            if (fact["id"] != f"WU-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != row_label
                    or fact["locator"] != locator):
                raise ValueError(f"WU selected fact definition differs: {fact['id']}")
            if _current_cell(rows, row_label, kind, end) != expected:
                raise ValueError(f"WU SEC actual-quarter cell differs: {fact['id']}")
            values[metric] = expected
        selected[role] = values
    for role, values in selected.items():
        if values["gaap_cost_of_services"] + values["gaap_selling_general_administrative"] != values["gaap_total_expenses"]:
            raise ValueError(f"WU operating-expense bridge differs: {role}")
        if values["gaap_revenues"] - values["gaap_total_expenses"] != values["gaap_operating_income"]:
            raise ValueError(f"WU operating-income bridge differs: {role}")
        if (values["gaap_operating_income"] + values["gaap_total_other_expense_net_signed"]
                != values["gaap_income_before_income_taxes"]):
            raise ValueError(f"WU pre-tax bridge differs: {role}")
        if values["gaap_income_before_income_taxes"] - values["gaap_provision_for_income_taxes"] != values["gaap_net_income"]:
            raise ValueError(f"WU tax/net-income bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_revenues": Decimal("6.5"),
        "gaap_cost_of_services": Decimal("0.4"),
        "gaap_selling_general_administrative": Decimal("-3.1"),
        "gaap_total_expenses": Decimal("-2.7"),
        "gaap_operating_income": Decimal("9.2"),
        "gaap_total_other_expense_net_signed": Decimal("-1.3"),
        "gaap_income_before_income_taxes": Decimal("7.9"),
        "gaap_provision_for_income_taxes": Decimal("-9.6"),
        "gaap_net_income": Decimal("17.5"),
        "gaap_diluted_eps": Decimal("0.06"),
        "gaap_weighted_average_diluted_shares": Decimal("-6.8"),
    }:
        raise ValueError("WU selected Q3-minus-Q2 changes differ")
    return {"status": "wu_actual_quarter_gaap_bridge_excludes_outlook",
            "selected_facts": 22, "net_income_delta_usd_million": "17.5",
            "operating_income_delta_usd_million": "9.2", "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
