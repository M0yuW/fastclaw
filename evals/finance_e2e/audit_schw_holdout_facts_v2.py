#!/usr/bin/env python3
"""Audit SCHW source-row mix and common-available income without GAAP/adjusted mixing."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "schw_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)")
EXPECTED = {
    "gaap_net_interest_revenue": ("NII", (2822, 3050), "USD_million_rounded", "Net interest revenue", "revenue"),
    "gaap_asset_management_administration_fees":
        ("ASSET", (1570, 1673), "USD_million_rounded", "Asset management and administration fees", "revenue"),
    "gaap_trading_revenue": ("TRADE", (952, 995), "USD_million_rounded", "Trading revenue", "revenue"),
    "gaap_bank_deposit_account_fees":
        ("BANK", (247, 247), "USD_million_rounded", "Bank deposit account fees", "revenue"),
    "gaap_other_revenue": ("OTHERREV", (260, 170), "USD_million_rounded", "Other", "revenue"),
    "gaap_total_net_revenues": ("REV", (5851, 6135), "USD_million_rounded", "Total net revenues", "statement"),
    "gaap_expenses_excluding_interest":
        ("EXP", (3048, 3114), "USD_million_rounded", "Total expenses excluding interest", "statement"),
    "gaap_income_before_taxes":
        ("PRETAX", (2803, 3021), "USD_million_rounded", "Income before taxes on income", "statement"),
    "gaap_taxes_on_income": ("TAX", (677, 663), "USD_million_rounded", "Taxes on income", "statement"),
    "gaap_net_income": ("NET", (2126, 2358), "USD_million_rounded", "Net Income", "statement"),
    "gaap_preferred_stock_dividends_and_other":
        ("PREF", (149, 81), "USD_million_rounded", "Preferred stock dividends and other", "statement"),
    "gaap_net_income_available_to_common":
        ("COMMON", (1977, 2277), "USD_million_rounded",
         "Net Income Available to Common Stockholders", "statement"),
    "gaap_diluted_eps": ("EPS", (1.08, 1.26), "USD_per_share_reported", "Diluted", "eps"),
    "gaap_weighted_average_diluted_common_shares":
        ("SHARES", (1822, 1811), "million_shares_reported", "Diluted", "shares"),
    "non_gaap_adjusted_net_income":
        ("ADJNET", (2222, 2456), "USD_million_rounded", "Adjusted", "adjusted"),
}
REVENUE_COMPONENTS = ("gaap_net_interest_revenue",
                      "gaap_asset_management_administration_fees",
                      "gaap_trading_revenue", "gaap_bank_deposit_account_fees",
                      "gaap_other_revenue")
CROSS_FILING = {
    "Net interest revenue": (3050, 2822),
    "Asset management and administration fees": (1673, 1570),
    "Trading revenue": (995, 952),
    "Bank deposit account fees": (247, 247),
    "Other": (170, 260),
    "Total net revenues": (6135, 5851),
    "Total expenses excluding interest": (3114, 3048),
    "Income before taxes on income": (3021, 2803),
    "Taxes on income": (663, 677),
    "Net Income": (2358, 2126),
    "Preferred stock dividends and other": (81, 149),
    "Net Income Available to Common Stockholders": (2277, 1977),
}


def _number(cell: str) -> Decimal:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not a SCHW financial cell: {cell!r}")
    value = cell.replace(",", "")
    if value.startswith("("):
        value = "-" + value[1:-1]
    return Decimal(value)


def _cell(rows: list[list[str]], row_label: str, section: str, quarter_end: str) -> Decimal:
    if (len(rows) < 84 or f"Three Months Ended{quarter_end}" not in rows[22][1]
            or rows[23][1] != "2025" or rows[60][0] != "(In millions, except per share amounts and as noted)"):
        raise ValueError("SCHW actual-quarter header/unit differs")
    bounds = {"revenue": (25, 33), "statement": (25, 49), "shares": (49, 52),
              "eps": (52, 55), "adjusted": (8, 11)}
    start, stop = bounds[section]
    matches = [row for row in rows[start:stop] if row and row[0] == row_label]
    if len(matches) != 1:
        raise ValueError(f"SCHW source row missing/ambiguous: {row_label} {section}")
    values = [cell for cell in matches[0][1:] if NUMBER.fullmatch(cell)]
    if len(values) < 2:
        raise ValueError(f"SCHW source row lacks comparison: {row_label}")
    return _number(values[0])


def _cross_filing_q2(rows: list[list[str]]) -> None:
    if "Third" not in rows[59] or "Second" not in rows[59]:
        raise ValueError("SCHW financial-highlight quarter sequence differs")
    for label, (q3, q2) in CROSS_FILING.items():
        region = rows[61:68] if label == "Other" else rows[61:84]
        matches = [row for row in region if row and row[0] == label]
        if len(matches) != 1:
            raise ValueError(f"SCHW Q3/Q2 highlight row missing/ambiguous: {label}")
        levels = [_number(cell) for cell in matches[0][8:] if NUMBER.fullmatch(cell)]
        if len(levels) < 2 or levels[:2] != [Decimal(q3), Decimal(q2)]:
            raise ValueError(f"SCHW Q3 exhibit Q2 comparator differs: {label}")


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "SCHW"
            or packet.get("cik") != "0000316709"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected SCHW packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, period_end, filed_at in (
        ("baseline", "HOLDOUT-SCHW-BASELINE-v1", "Q2", "June 30,", "06-30", "2025-07-18"),
        ("event", "HOLDOUT-SCHW-EVENT-v1", "Q3", "September 30,", "09-30", "2025-10-16"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{period_end}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"SCHW filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"SCHW selected metric set differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, row_label, kind = EXPECTED[metric]
            expected = Decimal(str(pair[0 if quarter == "Q2" else 1]))
            section_name = {"revenue": "Statement revenue section", "statement": "Statement",
                            "shares": "Statement weighted-average shares", "eps": "Statement EPS",
                            "adjusted": "Financial Highlights net income"}[kind]
            if kind == "revenue" and metric != "gaap_other_revenue":
                section_name = "Statement"
            locator = f"{section_name} / Three Months Ended {end} 2025"
            if (fact["id"] != f"SCHW-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != row_label
                    or fact["locator"] != locator):
                raise ValueError(f"SCHW selected fact definition differs: {fact['id']}")
            if _cell(rows, row_label, kind, end) != expected:
                raise ValueError(f"SCHW SEC standalone-quarter cell differs: {fact['id']}")
            values[metric] = expected
        if quarter == "Q3":
            _cross_filing_q2(rows)
        selected[role] = values
    for role, values in selected.items():
        if sum((values[metric] for metric in REVENUE_COMPONENTS), Decimal(0)) != values["gaap_total_net_revenues"]:
            raise ValueError(f"SCHW revenue mix differs: {role}")
        if values["gaap_total_net_revenues"] - values["gaap_expenses_excluding_interest"] != values["gaap_income_before_taxes"]:
            raise ValueError(f"SCHW pretax bridge differs: {role}")
        if values["gaap_income_before_taxes"] - values["gaap_taxes_on_income"] != values["gaap_net_income"]:
            raise ValueError(f"SCHW tax bridge differs: {role}")
        if (values["gaap_net_income"] - values["gaap_preferred_stock_dividends_and_other"]
                != values["gaap_net_income_available_to_common"]):
            raise ValueError(f"SCHW common-available bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if (delta["gaap_total_net_revenues"] != 284
            or delta["gaap_net_interest_revenue"] != 228
            or delta["gaap_asset_management_administration_fees"] != 103
            or delta["gaap_trading_revenue"] != 43
            or delta["gaap_bank_deposit_account_fees"] != 0
            or delta["gaap_other_revenue"] != -90
            or delta["gaap_expenses_excluding_interest"] != 66
            or delta["gaap_income_before_taxes"] != 218
            or delta["gaap_taxes_on_income"] != -14
            or delta["gaap_net_income"] != 232
            or delta["gaap_preferred_stock_dividends_and_other"] != -68
            or delta["gaap_net_income_available_to_common"] != 300
            or delta["gaap_diluted_eps"] != Decimal("0.18")
            or delta["gaap_weighted_average_diluted_common_shares"] != -11
            or delta["non_gaap_adjusted_net_income"] != 234):
        raise ValueError("SCHW selected Q3-minus-Q2 changes differ")
    return {"status": "schw_gaap_revenue_common_income_and_adjusted_separate",
            "selected_facts": 30, "q2_cross_filing_comparators": len(CROSS_FILING),
            "gaap_net_revenue_delta_usd_million": 284,
            "gaap_common_income_delta_usd_million": 300,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
