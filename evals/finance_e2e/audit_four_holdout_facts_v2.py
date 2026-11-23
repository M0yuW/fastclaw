#!/usr/bin/env python3
"""Audit FOUR appendix rows, excluding draft narrative and incomparable adjusted income."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_blocks import extract_blocks


PACKET = ROOT / "four_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMBER = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
EXPECTED = {
    "gaap_payments_based_revenue": ("PAY", (772.4, 755.7), "USD_million_rounded",
                                    "Payments-based revenue", "revenue"),
    "gaap_subscription_other_revenue": ("SUB", (114.6, 92.6), "USD_million_rounded",
                                        "Subscription and other revenues", "revenue"),
    "gaap_gross_revenue": ("REV", (887.0, 848.3), "USD_million_rounded",
                           "GROSS REVENUE", "revenue"),
    "gaap_network_fees_signed": ("NETFEES", (-482.0, -479.8), "USD_million_rounded",
                                 "Less: Network fees", "revenue"),
    "gaap_gross_profit": ("GROSS", (270.8, 240.7), "USD_million_rounded",
                          "GROSS PROFIT", "revenue"),
    "non_gaap_gross_revenue_less_network_fees":
        ("GRLNF", (405.0, 368.5), "USD_million_rounded",
         "GROSS REVENUE LESS NETWORK FEES", "revenue"),
    "gaap_income_from_operations": ("OPINC", (86.0, 25.4), "USD_million_rounded",
                                    "Income from operations", "statement"),
    "gaap_gain_on_investments_in_securities":
        ("GAIN", (45.1, 0.3), "USD_million_rounded",
         "Gain on investments in securities", "statement"),
    "gaap_net_income": ("NET", (139.3, 19.5), "USD_million_rounded",
                        "Net income", "statement"),
    "gaap_noncontrolling_income_signed":
        ("NCI", (-23.3, -2.8), "USD_million_rounded",
         "Less: Net income attributable to noncontrolling interests", "statement"),
    "gaap_net_income_attributable_to_shift4":
        ("ATTR", (116.0, 16.7), "USD_million_rounded",
         "Net income attributable to Shift4 Payments, Inc.", "statement"),
    "gaap_class_a_diluted_eps":
        ("EPS", (1.44, 0.20), "USD_per_share_reported",
         "Class A net income per share - diluted", "statement"),
    "non_gaap_adjusted_ebitda":
        ("ADJEBITDA", (205.9, 168.5), "USD_million_rounded",
         "ADJUSTED EBITDA", "adjusted"),
}
REVENUE_COMPONENTS = ("gaap_payments_based_revenue", "gaap_subscription_other_revenue")


def _signed(cell: str) -> Decimal:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not a FOUR financial cell: {cell!r}")
    raw = cell.replace(",", "")
    if raw.startswith("("):
        raw = "-" + raw[1:-1]
    return Decimal(raw)


def _one_block(blocks: list[str], heading: str) -> str:
    matches = [block for block in blocks if block.startswith(heading)]
    if len(matches) != 1:
        raise ValueError(f"FOUR financial appendix missing/ambiguous: {heading}")
    return matches[0]


def _current_row(block: str, label: str) -> Decimal:
    pattern = re.compile(r"(?<![\w])" + re.escape(label)
                         + r"\s+\$?\s*(\(?-?\d[\d,]*(?:\.\d+)?\)?)")
    matches = list(pattern.finditer(block))
    if not matches:
        raise ValueError(f"FOUR appendix row missing: {label}")
    return _signed(matches[0].group(1))


def _adjusted_last(block: str, label: str) -> list[Decimal]:
    match = re.search(re.escape(label) + r"\s+\$\s*(.+?)(?=\s+"
                      + re.escape(label) + r"\s+\$|\s+GROSS REVENUE LESS NETWORK FEES|\s+\(A\))", block)
    if match is None:
        raise ValueError(f"FOUR adjusted reconciliation row missing: {label}")
    values = [_signed(cell) for cell in NUMBER.findall(match.group(1))]
    if len(values) != 5:
        raise ValueError(f"FOUR adjusted reconciliation has wrong period count: {label}")
    return values


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "FOUR"
            or packet.get("cik") != "0001794669"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected FOUR packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    adjusted_blocks = {}
    for role, source_id, quarter, period, end, filed_at, heading in (
        ("baseline", "HOLDOUT-FOUR-BASELINE-v1", "Q4", "CY2024", "December 31, 2024",
         "2025-02-18", "Fourth Quarter of 2024"),
        ("event", "HOLDOUT-FOUR-EVENT-v1", "Q1", "CY2025", "March 31, 2025",
         "2025-04-29", "First Quarter of 2025"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"{period} {quarter} ended {end[-4:]}-"
                + ("12-31" if quarter == "Q4" else "03-31")
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"FOUR filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"FOUR selected metric set differs: {role}")
        blocks = extract_blocks(ROOT / source["local_path"])
        statement = _one_block(blocks, f"{heading} Condensed Consolidated Statements of Operations")
        revenue = _one_block(blocks, f"{heading} Reconciliations of Gross Revenue to Gross Profit")
        adjusted = _one_block(blocks, f"{heading} Reconciliations of Net Income to")
        if ("Three Months Ended" not in statement or end not in statement
                or "Three Months Ended" not in revenue or end not in revenue
                or "In millions, except share and per share data" not in statement):
            raise ValueError(f"FOUR financial appendix period/unit differs: {role}")
        adjusted_blocks[role] = adjusted
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, label, kind = EXPECTED[metric]
            expected = Decimal(str(pair[0 if quarter == "Q4" else 1]))
            locator = (f"Adjusted EBITDA reconciliation / {quarter} {end[-4:]}" if kind == "adjusted"
                       else f"{'Revenue reconciliation' if kind == 'revenue' else 'Statement'} "
                       f"/ Three Months Ended {end}")
            if (fact["id"] != f"FOUR-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != label
                    or fact["locator"] != locator):
                raise ValueError(f"FOUR selected fact definition differs: {fact['id']}")
            actual = (_adjusted_last(adjusted, "ADJUSTED EBITDA")[-1] if kind == "adjusted"
                      else _current_row(revenue if kind == "revenue" else statement, label))
            if actual != expected:
                raise ValueError(f"FOUR SEC appendix cell differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    old_adjusted = _adjusted_last(adjusted_blocks["baseline"], "ADJUSTED NET INCOME")[-1]
    new_adjusted_series = _adjusted_last(adjusted_blocks["event"], "ADJUSTED NET INCOME")
    if (old_adjusted != Decimal("123.4")
            or new_adjusted_series[-2:] != [Decimal("154.4"), Decimal("98.6")]
            or "Beginning in the first quarter of 2025, Shift4 began excluding" not in adjusted_blocks["event"]):
        raise ValueError("FOUR adjusted-net-income definition/restatement differs")
    if _adjusted_last(adjusted_blocks["event"], "ADJUSTED EBITDA")[-2] != Decimal("205.9"):
        raise ValueError("FOUR Q1 exhibit Q4 adjusted-EBITDA comparator differs")
    for role, values in selected.items():
        if sum((values[metric] for metric in REVENUE_COMPONENTS), Decimal(0)) != values["gaap_gross_revenue"]:
            raise ValueError(f"FOUR gross-revenue bridge differs: {role}")
        if values["gaap_gross_revenue"] + values["gaap_network_fees_signed"] != values["non_gaap_gross_revenue_less_network_fees"]:
            raise ValueError(f"FOUR GRLNF reconciliation differs: {role}")
        if values["gaap_net_income"] + values["gaap_noncontrolling_income_signed"] != values["gaap_net_income_attributable_to_shift4"]:
            raise ValueError(f"FOUR attributable-income bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_payments_based_revenue": Decimal("-16.7"),
        "gaap_subscription_other_revenue": Decimal("-22.0"),
        "gaap_gross_revenue": Decimal("-38.7"),
        "gaap_network_fees_signed": Decimal("2.2"),
        "gaap_gross_profit": Decimal("-30.1"),
        "non_gaap_gross_revenue_less_network_fees": Decimal("-36.5"),
        "gaap_income_from_operations": Decimal("-60.6"),
        "gaap_gain_on_investments_in_securities": Decimal("-44.8"),
        "gaap_net_income": Decimal("-119.8"),
        "gaap_noncontrolling_income_signed": Decimal("20.5"),
        "gaap_net_income_attributable_to_shift4": Decimal("-99.3"),
        "gaap_class_a_diluted_eps": Decimal("-1.24"),
        "non_gaap_adjusted_ebitda": Decimal("-37.4"),
    }:
        raise ValueError("FOUR selected Q1-minus-Q4 changes differ")
    return {"status": "four_appendix_only_adjacent_quarters_match",
            "selected_facts": 26, "adjusted_income_definition_change_checked": True,
            "gross_revenue_delta_usd_million": "-38.7",
            "gaap_attributable_delta_usd_million": "-99.3",
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
