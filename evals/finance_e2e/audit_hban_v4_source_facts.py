#!/usr/bin/env python3
"""Audit selected HBAN Q2/Q3 SEC rows and the Q3 prior-quarter column.

The inputs are frozen public-source bytes. This is a source audit, not an
agent-quality score or a model observation. GAAP and FTE/non-GAAP rows remain
separate, and the notable-item decomposition is only arithmetic.
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
PACKET = HERE / "hban_v4_source_fact_packet.json"
SELECTION = HERE / "postcorrection_v4_first4_sec_pairs.json"
FROZEN = HERE / "results/2026-10-24-postcorrection-v4-first4-exhibits-complete"
MANIFEST = FROZEN / "manifest.json"
NUMERIC = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")

# The locators refer to the hash-frozen HTML table order. Each row's exact
# label and the adjacent-period comparator are independently checked below.
ROWS = {
    "gaap_net_income_attributable_to_huntington":
        ("Net income attributable to Huntington", 4, 4),
    "gaap_diluted_eps": ("Diluted earnings per common share", 5, 5),
    "fte_net_interest_margin_percent": ("Net interest margin", 10, 10),
    "average_earning_assets": ("Average earning assets", 16, 16),
    "average_loans_and_leases": ("Average loans and leases", 17, 17),
    "average_total_deposits": ("Average total deposits", 18, 18),
    "reported_cet1_percent":
        ("Common equity Tier 1 risk-based capital ratio (1)", 21, 21),
    "gaap_net_interest_income": ("Net interest income", 54, 60),
    "fte_net_interest_income": ("Net interest income - FTE", 56, 62),
    "gaap_noninterest_income": ("Total noninterest income", 144, 150),
    "fte_total_revenue": ("Total revenue - FTE", 58, 64),
    "gaap_noninterest_expense": ("Total noninterest expense", 169, 177),
    "gaap_provision_for_credit_losses":
        ("Provision for credit losses", 216, 224),
    "reported_net_chargeoffs": ("Net charge-offs", 217, 225),
    "reported_net_chargeoff_rate_percent":
        ("Net charge-offs / Average total loans and leases", 218, 226),
    "reported_allowance_for_credit_losses":
        ("Allowance for credit losses (ACL)", 221, 229),
}


def numeric_cells(row: list[str]) -> list[Decimal]:
    return [displayed_number(cell) for cell in row[1:]
            if NUMERIC.fullmatch(cell)]


def audit(packet: dict | None = None) -> dict:
    packet = packet or json.loads(PACKET.read_text())
    selection = json.loads(SELECTION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    pair = next(item for item in selection["pairs"] if item["symbol"] == "HBAN")
    if (packet.get("version") != 4 or packet.get("paid_calls_authorized") is not False
            or packet.get("model_observations") != 0):
        raise ValueError("HBAN packet is not a source-only candidate")
    if "HBAN" in (set(prior.preflight()["selected_cik"])
                  | prior.observed_v1_symbols()):
        raise ValueError("HBAN overlaps prior observed issuer frame")
    if (set(packet["baseline"]["facts"]) != set(ROWS)
            or set(packet["event"]["facts"]) != set(ROWS)):
        raise ValueError("HBAN selected fact set differs")

    parsed = {}
    for role in ("baseline", "event"):
        section = packet[role]
        chosen = pair[role]
        entry = next(item for item in manifest["entries"]
                     if item["id"] == section["source_id"])
        source = FROZEN / f"HOLDOUT-V4-HBAN-{role.upper()}.htm"
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if (digest != entry["sha256"] or digest != section["source_sha256"]
                or entry["url"] != chosen["url"]
                or section["period"] != chosen["period"]):
            raise ValueError(f"{role} SEC source identity differs")
        html = SourceHTML()
        html.feed(source.read_text(errors="replace"))
        quarter = "Second" if role == "baseline" else "Third"
        if (f"Reports 2025 {quarter}-Quarter Earnings" not in html.text
                or html.rows[2][1] != quarter
                or "(in millions, except per share data)" not in html.rows[2][0]):
            raise ValueError(f"{role} quarter or displayed-unit header differs")
        parsed[role] = html

    for metric, (label, q2_row, q3_row) in ROWS.items():
        baseline_row = parsed["baseline"].rows[q2_row]
        event_row = parsed["event"].rows[q3_row]
        if baseline_row[0] != label or event_row[0] != label:
            raise ValueError(f"HBAN row locator differs: {metric}")
        before = Decimal(packet["baseline"]["facts"][metric])
        after = Decimal(packet["event"]["facts"][metric])
        q2_cells, q3_cells = numeric_cells(baseline_row), numeric_cells(event_row)
        if (len(q2_cells) < 2 or len(q3_cells) < 2
                or q2_cells[0] != before or q3_cells[0] != after
                or q3_cells[1] != before):
            raise ValueError(f"HBAN source value/comparator differs: {metric}")

    before = {key: Decimal(value) for key, value in packet["baseline"]["facts"].items()}
    after = {key: Decimal(value) for key, value in packet["event"]["facts"].items()}
    for facts in (before, after):
        if (facts["fte_net_interest_income"] + facts["gaap_noninterest_income"]
                != facts["fte_total_revenue"]):
            raise ValueError("HBAN FTE revenue identity differs")
    notable = packet["event"]["notable_item"]
    gain_row = parsed["event"].rows[153]
    adjusted_row = parsed["event"].rows[154]
    if (not gain_row[0].startswith("Gain on sale of a portion of corporate trust")
            or adjusted_row[0] != "Total adjusted noninterest income (Non-GAAP)"):
        raise ValueError("HBAN notable-item rows differ")
    gain = Decimal(notable["gaap_noninterest_income_gain_on_sale_usd_million"])
    adjusted = Decimal(notable["non_gaap_adjusted_noninterest_income_usd_million"])
    prior_adjusted = Decimal(notable[
        "non_gaap_adjusted_noninterest_income_prior_quarter_comparator_usd_million"])
    if (numeric_cells(gain_row)[0] != gain
            or numeric_cells(adjusted_row)[:2] != [adjusted, prior_adjusted]
            or after["gaap_noninterest_income"] - gain != adjusted
            or prior_adjusted != before["gaap_noninterest_income"]):
        raise ValueError("HBAN notable-item/adjusted comparison differs")
    return {
        "status": "hban_selected_source_rows_and_q2_comparators_audited",
        "selected_facts": 2 * len(ROWS),
        "q2_cross_filing_comparators": len(ROWS),
        "gaap_noninterest_income_delta_usd_million": str(
            after["gaap_noninterest_income"] - before["gaap_noninterest_income"]),
        "q3_notable_gain_usd_million": str(gain),
        "q3_adjusted_noninterest_income_delta_usd_million": str(
            adjusted - prior_adjusted),
        "model_observations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
