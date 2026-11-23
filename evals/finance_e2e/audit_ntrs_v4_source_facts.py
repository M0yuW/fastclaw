#!/usr/bin/env python3
"""Audit NTRS current-quarter SEC rows and repeated Q2 comparator cells.

The signed negative Q3 provision is retained as reported. FTE measures are
not interchanged with GAAP. This checks public source data, not agent output.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from audit_wex_v4_source_facts import SourceHTML, displayed_number
import rank_postcorrection_holdout_v2 as prior


HERE = Path(__file__).parent
PACKET = HERE / "ntrs_v4_source_fact_packet.json"
SELECTION = HERE / "postcorrection_v4_first4_sec_pairs.json"
FROZEN = HERE / "results/2026-10-24-postcorrection-v4-first4-exhibits-complete"
MANIFEST = FROZEN / "manifest.json"
NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")

ROWS = {
    "gaap_trust_investment_servicing_fees":
        ("Trust, Investment and Other Servicing Fees", 12),
    "gaap_other_noninterest_income": ("Other Noninterest Income (1)", 13),
    "gaap_net_interest_income": ("Net Interest Income - GAAP", 211),
    "non_gaap_fte_net_interest_income":
        ("Net Interest Income (FTE) - Non-GAAP", 213),
    "gaap_total_revenue": ("Total Revenue - GAAP", 219),
    "non_gaap_fte_total_revenue": ("Total Revenue (FTE) - Non-GAAP", 221),
    "gaap_noninterest_expense": ("Total Noninterest Expense", 280),
    "gaap_provision_for_credit_losses_signed":
        ("Provision for Credit Losses", 18),
    "gaap_provision_for_income_taxes": ("Provision for Income Taxes", 19),
    "gaap_net_income": ("Net Income", 21),
    "gaap_diluted_eps": ("Diluted Earnings per Common Share", 24),
    "reported_assets_under_custody_administration_usd_billion":
        ("Total Assets Under Custody/Administration", 37),
    "reported_assets_under_management_usd_billion":
        ("Total Assets Under Management", 45),
    "gaap_net_interest_margin_percent": ("Net Interest Margin - GAAP (1)", 215),
    "non_gaap_fte_net_interest_margin_percent":
        ("Net Interest Margin (FTE) - Non-GAAP (1)", 216),
    "gaap_asset_servicing_trust_fees":
        ("Total Asset Servicing Trust, Investment and Other Servicing Fees", 56),
    "gaap_wealth_management_trust_fees":
        ("Total Wealth Management Trust, Investment and Other Servicing Fees", 63),
}


def numeric_cells(row: list[str]) -> list[Decimal]:
    return [displayed_number(cell) for cell in row[1:] if NUMBER.fullmatch(cell)]


def audit(packet: dict | None = None) -> dict:
    packet = packet or json.loads(PACKET.read_text())
    selection = json.loads(SELECTION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    pair = next(item for item in selection["pairs"] if item["symbol"] == "NTRS")
    if (packet.get("version") != 4 or packet.get("paid_calls_authorized") is not False
            or packet.get("model_observations") != 0):
        raise ValueError("NTRS packet is not a source-only candidate")
    if "NTRS" in (set(prior.preflight()["selected_cik"])
                  | prior.observed_v1_symbols()):
        raise ValueError("NTRS overlaps prior observed issuer frame")
    if (set(packet["baseline"]["facts"]) != set(ROWS)
            or set(packet["event"]["facts"]) != set(ROWS)):
        raise ValueError("NTRS selected fact set differs")

    parsed = {}
    for role, quarter, month in (("baseline", "Q2", "June"),
                                 ("event", "Q3", "September")):
        section = packet[role]
        chosen = pair[role]
        entry = next(item for item in manifest["entries"]
                     if item["id"] == section["source_id"])
        path = FROZEN / f"HOLDOUT-V4-NTRS-{role.upper()}.htm"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if (digest != entry["sha256"] or digest != section["source_sha256"]
                or entry["url"] != chosen["url"]
                or section["period"] != chosen["period"]):
            raise ValueError(f"{role} SEC source identity differs")
        html = SourceHTML()
        html.feed(path.read_text(errors="replace"))
        if (html.rows[11][0] != "($ In Millions except per share data)"
                or html.rows[11][1] != f"{quarter} 2025"
                or html.rows[33][0] != "($ In Billions)"
                or month not in html.rows[33][1]):
            raise ValueError(f"{role} source table period/unit header differs")
        if role == "event" and html.rows[11][2] != "Q2 2025":
            raise ValueError("event prior-quarter comparator header differs")
        parsed[role] = html

    for metric, (label, index) in ROWS.items():
        before_row = parsed["baseline"].rows[index]
        after_row = parsed["event"].rows[index]
        if before_row[0] != label or after_row[0] != label:
            raise ValueError(f"NTRS row locator differs: {metric}")
        old = Decimal(packet["baseline"]["facts"][metric])
        new = Decimal(packet["event"]["facts"][metric])
        q2_values, q3_values = numeric_cells(before_row), numeric_cells(after_row)
        if (len(q2_values) < 2 or len(q3_values) < 2
                or q2_values[0] != old or q3_values[0] != new
                or q3_values[1] != old):
            raise ValueError(f"NTRS source value/comparator differs: {metric}")

    for role in ("baseline", "event"):
        facts = {key: Decimal(value) for key, value in packet[role]["facts"].items()}
        noninterest = (facts["gaap_trust_investment_servicing_fees"]
                       + facts["gaap_other_noninterest_income"])
        if (noninterest + facts["gaap_net_interest_income"]
                != facts["gaap_total_revenue"]
                or noninterest + facts["non_gaap_fte_net_interest_income"]
                != facts["non_gaap_fte_total_revenue"]
                or facts["gaap_asset_servicing_trust_fees"]
                + facts["gaap_wealth_management_trust_fees"]
                != facts["gaap_trust_investment_servicing_fees"]
                or facts["gaap_total_revenue"] - facts["gaap_noninterest_expense"]
                - facts["gaap_provision_for_credit_losses_signed"]
                - facts["gaap_provision_for_income_taxes"]
                != facts["gaap_net_income"]):
            raise ValueError(f"{role} displayed income-statement bridge differs")
    before = packet["baseline"]["facts"]
    after = packet["event"]["facts"]
    return {
        "status": "ntrs_source_cells_comparators_basis_and_signed_bridge_audited",
        "selected_facts": 2 * len(ROWS),
        "q2_cross_filing_comparators": len(ROWS),
        "gaap_revenue_delta_usd_million": str(
            Decimal(after["gaap_total_revenue"]) - Decimal(before["gaap_total_revenue"])),
        "gaap_nii_delta_usd_million": str(
            Decimal(after["gaap_net_interest_income"])
            - Decimal(before["gaap_net_interest_income"])),
        "signed_provision_delta_usd_million": str(
            Decimal(after["gaap_provision_for_credit_losses_signed"])
            - Decimal(before["gaap_provision_for_credit_losses_signed"])),
        "model_observations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
