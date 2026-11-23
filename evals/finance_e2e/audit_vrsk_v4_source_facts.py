#!/usr/bin/env python3
"""Audit VRSK SEC quarterly cells, signed GAAP identities and guidance.

The source exhibits use current-quarter and prior-year columns. Only the
current Q2 and current Q3 columns of their respective releases are compared;
the resulting deltas are sequential, not year-over-year.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from audit_wex_v4_source_facts import SourceHTML
import rank_postcorrection_holdout_v2 as prior


HERE = Path(__file__).parent
PACKET = HERE / "vrsk_v4_source_fact_packet.json"
SELECTION = HERE / "postcorrection_v4_first4_sec_pairs.json"
FROZEN = HERE / "results/2026-10-24-postcorrection-v4-first4-exhibits-complete"
MANIFEST = FROZEN / "manifest.json"
SOURCE_NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
RANGE_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

ROWS = {
    "gaap_revenues": ("Revenues", 119, 118),
    "gaap_total_operating_expenses": ("Total operating expenses, net", 125, 124),
    "gaap_operating_income": ("Operating income", 126, 125),
    "gaap_income_before_taxes": ("Income before income taxes", 132, 131),
    "gaap_tax_expense_magnitude": ("Provision for income taxes", 133, 132),
    "gaap_net_income": ("Net income", 134, 133),
    "gaap_diluted_eps":
        ("Diluted net income per share attributable to Verisk:", 138, 137),
    "non_gaap_adjusted_ebitda": ("Adjusted EBITDA", 233, 238),
    "non_gaap_adjusted_net_income": ("Adjusted net income", 283, 298),
    "non_gaap_organic_revenues": ("Organic revenues", 227, 231),
    "non_gaap_free_cash_flow": ("Free cash flow", 56, 55),
}

GUIDANCE = {
    "updated_full_year_revenue_usd_million_range": ("Total revenue", 63, 62),
    "updated_full_year_adjusted_ebitda_usd_million_range":
        ("Adjusted EBITDA", 64, 63),
    "updated_full_year_adjusted_eps_usd_per_share_range":
        ("Diluted adjusted EPS", 66, 65),
}


def first_number(row: list[str]) -> Decimal:
    for cell in row[1:]:
        if SOURCE_NUMBER.fullmatch(cell):
            amount = Decimal(cell.strip("()").replace(",", ""))
            return -amount if cell.startswith("(") else amount
    raise ValueError(f"numeric SEC cell missing: {row[0] if row else 'row'}")


def guidance_range(cell: str) -> list[Decimal]:
    values = [Decimal(item.replace(",", "")) for item in RANGE_NUMBER.findall(cell)]
    if len(values) != 2 or values[0] > values[1]:
        raise ValueError(f"invalid source guidance range: {cell!r}")
    return values


def audit(packet: dict | None = None) -> dict:
    packet = packet or json.loads(PACKET.read_text())
    selection = json.loads(SELECTION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    pair = next(item for item in selection["pairs"] if item["symbol"] == "VRSK")
    if (packet.get("version") != 4 or packet.get("paid_calls_authorized") is not False
            or packet.get("model_observations") != 0):
        raise ValueError("VRSK packet is not a source-only candidate")
    if "VRSK" in (set(prior.preflight()["selected_cik"])
                  | prior.observed_v1_symbols()):
        raise ValueError("VRSK overlaps prior observed issuer frame")
    parsed = {}
    for role, month, quarter, heading, year in (
            ("baseline", "June", "Second", 116, 117),
            ("event", "September", "Third", 115, 116)):
        section = packet[role]
        chosen = pair[role]
        entry = next(item for item in manifest["entries"]
                     if item["id"] == section["source_id"])
        path = FROZEN / f"HOLDOUT-V4-VRSK-{role.upper()}.htm"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (digest != entry["sha256"] or digest != section["source_sha256"]
                or entry["url"] != chosen["url"]
                or section["period"] != chosen["period"]):
            raise ValueError(f"{role} SEC source identity differs")
        html = SourceHTML()
        html.feed(path.read_text(errors="replace"))
        if (f"Verisk Reports {quarter}-Quarter 2025 Financial Results" not in html.text
                or f"Three Months Ended {month} 30," not in html.rows[heading]
                or "2025" not in html.rows[year]
                or "2024" not in html.rows[year]
                or "(in millions, except for share and per share data)"
                not in html.rows[year + 1]):
            raise ValueError(f"{role} current-quarter statement header differs")
        parsed[role] = html

    if (set(packet["baseline"]["facts"]) != set(ROWS)
            or set(packet["event"]["facts"]) != set(ROWS)):
        raise ValueError("VRSK selected fact set differs")
    for metric, (label, q2_row, q3_row) in ROWS.items():
        for role, index in (("baseline", q2_row), ("event", q3_row)):
            row = parsed[role].rows[index]
            if row[0] != label:
                raise ValueError(f"{role} source row locator differs: {metric}")
            observed = first_number(row)
            declared = Decimal(packet[role]["facts"][metric])
            if metric == "gaap_tax_expense_magnitude":
                observed = -observed  # SEC statement prints the expense in parentheses.
            if observed != declared:
                raise ValueError(f"{role} selected source value differs: {metric}")

    for role in ("baseline", "event"):
        facts = {key: Decimal(value) for key, value in packet[role]["facts"].items()}
        if (facts["gaap_revenues"] - facts["gaap_total_operating_expenses"]
                != facts["gaap_operating_income"]
                or facts["gaap_income_before_taxes"]
                - facts["gaap_tax_expense_magnitude"] != facts["gaap_net_income"]):
            raise ValueError(f"{role} displayed GAAP bridge differs")

    if (set(packet["baseline"]["guidance"]) != set(GUIDANCE)
            or set(packet["event"]["guidance"]) != set(GUIDANCE)):
        raise ValueError("VRSK selected guidance set differs")
    for metric, (label, q2_row, q3_row) in GUIDANCE.items():
        q2 = parsed["baseline"].rows[q2_row]
        q3 = parsed["event"].rows[q3_row]
        if q2[0] != label or q3[0] != label:
            raise ValueError(f"VRSK guidance row locator differs: {metric}")
        before = [Decimal(value) for value in packet["baseline"]["guidance"][metric]]
        after = [Decimal(value) for value in packet["event"]["guidance"][metric]]
        if (guidance_range(q2[5]) != before or guidance_range(q3[2]) != before
                or guidance_range(q3[3]) != after):
            raise ValueError(f"VRSK guidance chronology differs: {metric}")

    before = packet["baseline"]["facts"]
    after = packet["event"]["facts"]
    return {
        "status": "vrsk_current_quarter_source_facts_gaap_bridges_and_guidance_audited",
        "selected_facts": 2 * len(ROWS),
        "guidance_ranges_checked": 2 * len(GUIDANCE),
        "gaap_revenue_sequential_delta_usd_million": str(
            Decimal(after["gaap_revenues"]) - Decimal(before["gaap_revenues"])),
        "gaap_net_income_sequential_delta_usd_million": str(
            Decimal(after["gaap_net_income"]) - Decimal(before["gaap_net_income"])),
        "model_observations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
