#!/usr/bin/env python3
"""Audit IBKR consolidated-to-common income bridge against locked SEC releases."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "ibkr_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)")
EXPECTED = {
    "gaap_commissions": ("COMM", (516, 537), "USD_million_rounded", "Commissions", "statement"),
    "gaap_other_fees_services": ("FEES", (62, 66), "USD_million_rounded", "Other fees and services", "statement"),
    "gaap_other_income":
        ("OTHER", (42, 85), "USD_million_rounded", ("Other income (loss)", "Other income"), "statement"),
    "gaap_total_noninterest_income":
        ("NONINT", (620, 688), "USD_million_rounded", "Total non-interest income", "statement"),
    "gaap_total_net_interest_income":
        ("NII", (860, 967), "USD_million_rounded", "Total net interest income", "statement"),
    "gaap_total_net_revenues":
        ("REV", (1480, 1655), "USD_million_rounded", "Total net revenues", "statement"),
    "gaap_total_noninterest_expenses":
        ("EXP", (376, 343), "USD_million_rounded", "Total non-interest expenses", "statement"),
    "gaap_income_before_taxes":
        ("PRETAX", (1104, 1312), "USD_million_rounded", "Income before income taxes", "statement"),
    "gaap_income_tax_expense":
        ("TAX", (98, 126), "USD_million_rounded", "Income tax expense", "statement"),
    "gaap_consolidated_net_income":
        ("NET", (1006, 1186), "USD_million_rounded", "Net income", "statement"),
    "gaap_net_income_noncontrolling_interests":
        ("NCI", (782, 923), "USD_million_rounded",
         "Net income attributable to noncontrolling interests", "statement"),
    "gaap_net_income_available_common":
        ("COMMON", (224, 263), "USD_million_rounded",
         "Net income available for common stockholders", "statement"),
    "gaap_diluted_eps":
        ("EPS", (0.51, 0.59), "USD_per_share_reported", "Diluted", "eps"),
}
NONINTEREST_COMPONENTS = ("gaap_commissions", "gaap_other_fees_services", "gaap_other_income")
REVENUE_COMPONENTS = ("gaap_total_noninterest_income", "gaap_total_net_interest_income")


def _number(cell: str) -> Decimal:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not an IBKR financial cell: {cell!r}")
    value = cell.replace(",", "")
    if value.startswith("("):
        value = "-" + value[1:-1]
    return Decimal(value)


def _current_cell(rows: list[list[str]], label: str, section: str, end: str) -> Decimal:
    if (len(rows) < 44 or rows[12][4] != "Three Months"
            or rows[13][4] != f"Ended {end}" or rows[14][4] != "2025"
            or rows[15][4] != "(in millions, except share and per share data)"):
        raise ValueError("IBKR standalone-quarter header/unit differs")
    start, stop = (17, 38) if section == "statement" else (38, 41)
    matches = [row for row in rows[start:stop] if label in row[:3]]
    if len(matches) != 1:
        raise ValueError(f"IBKR source row missing/ambiguous: {label} {section}")
    values = [cell for cell in matches[0][1:] if NUMBER.fullmatch(cell)]
    if len(values) < 2:
        raise ValueError(f"IBKR source row lacks comparison column: {label}")
    return _number(values[0])


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "IBKR"
            or packet.get("cik") != "0001381197"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected IBKR packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, period_end, filed_at in (
        ("baseline", "HOLDOUT-IBKR-BASELINE-v1", "Q2", "June 30,", "06-30", "2025-07-17"),
        ("event", "HOLDOUT-IBKR-EVENT-v1", "Q3", "September 30,", "09-30", "2025-10-16"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{period_end}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"IBKR filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"IBKR selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        if quarter == "Q2" and "approximately $26 million one-time credit" not in rows[1][1]:
            raise ValueError("IBKR Q2 NII one-time-credit disclosure differs")
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, labels, kind = EXPECTED[metric]
            expected = Decimal(str(pair[0 if quarter == "Q2" else 1]))
            label = labels[0 if quarter == "Q2" else 1] if isinstance(labels, tuple) else labels
            locator = f"{'Statement' if kind == 'statement' else 'Statement EPS'} / Three Months Ended {end} 2025"
            if (fact["id"] != f"IBKR-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != label
                    or fact["locator"] != locator):
                raise ValueError(f"IBKR selected fact definition differs: {fact['id']}")
            if _current_cell(rows, label, kind, end) != expected:
                raise ValueError(f"IBKR SEC standalone-quarter cell differs: {fact['id']}")
            values[metric] = expected
        selected[role] = values
    for role, values in selected.items():
        if sum((values[metric] for metric in NONINTEREST_COMPONENTS), Decimal(0)) != values["gaap_total_noninterest_income"]:
            raise ValueError(f"IBKR non-interest-income components differ: {role}")
        if sum((values[metric] for metric in REVENUE_COMPONENTS), Decimal(0)) != values["gaap_total_net_revenues"]:
            raise ValueError(f"IBKR net-revenue bridge differs: {role}")
        if values["gaap_total_net_revenues"] - values["gaap_total_noninterest_expenses"] != values["gaap_income_before_taxes"]:
            raise ValueError(f"IBKR pre-tax bridge differs: {role}")
        if values["gaap_income_before_taxes"] - values["gaap_income_tax_expense"] != values["gaap_consolidated_net_income"]:
            raise ValueError(f"IBKR tax bridge differs: {role}")
        if (values["gaap_consolidated_net_income"] - values["gaap_net_income_noncontrolling_interests"]
                != values["gaap_net_income_available_common"]):
            raise ValueError(f"IBKR common-available bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_commissions": Decimal(21),
        "gaap_other_fees_services": Decimal(4),
        "gaap_other_income": Decimal(43),
        "gaap_total_noninterest_income": Decimal(68),
        "gaap_total_net_interest_income": Decimal(107),
        "gaap_total_net_revenues": Decimal(175),
        "gaap_total_noninterest_expenses": Decimal(-33),
        "gaap_income_before_taxes": Decimal(208),
        "gaap_income_tax_expense": Decimal(28),
        "gaap_consolidated_net_income": Decimal(180),
        "gaap_net_income_noncontrolling_interests": Decimal(141),
        "gaap_net_income_available_common": Decimal(39),
        "gaap_diluted_eps": Decimal("0.08"),
    }:
        raise ValueError("IBKR selected Q3-minus-Q2 changes differ")
    return {"status": "ibkr_consolidated_and_common_income_separated",
            "selected_facts": 26, "consolidated_net_delta_usd_million": 180,
            "common_available_delta_usd_million": 39,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
