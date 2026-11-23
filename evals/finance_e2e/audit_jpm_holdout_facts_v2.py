#!/usr/bin/env python3
"""Audit JPM firmwide reported/managed rows and the Q2 comparator in Q3."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines
from sec_html_rows import extract_rows


PACKET = ROOT / "jpm_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\d[\d,]*(?:\.\d+)?")
EXPECTED = {
    "gaap_reported_net_revenue": (44912, 46427, "REVREP", "Net revenue - reported", "USD_million_rounded"),
    "non_gaap_managed_net_revenue": (45680, 47120, "REVMAN", "Net revenue - managed", "USD_million_rounded"),
    "gaap_noninterest_expense": (23779, 24281, "OPEX", "Noninterest expense", "USD_million_rounded"),
    "gaap_provision_for_credit_losses": (2849, 3403, "PROV", "Provision for credit losses", "USD_million_rounded"),
    "gaap_net_income": (14987, 14393, "NET", "Net income", "USD_million_rounded"),
    "gaap_diluted_eps": (Decimal("5.24"), Decimal("5.07"), "EPS", "Earnings per share - diluted", "USD_per_share_reported"),
}


def _firmwide_cells(rows: list[list[str]], label: str, current: str, prior: str) -> list[Decimal]:
    starts = [i for i, row in enumerate(rows[:30]) if row and row[0] == "Results for JPM"]
    if len(starts) != 1:
        raise ValueError("JPM firmwide Results for JPM section missing/ambiguous")
    start = starts[0]
    header = rows[start + 1]
    if (not header or current not in header or prior not in header
            or header.index(current) >= header.index(prior)):
        raise ValueError("JPM firmwide current/prior quarter header differs")
    matches = [row for row in rows[start + 2:start + 10] if row and row[0] == label]
    if len(matches) != 1:
        raise ValueError(f"JPM firmwide selected row missing/ambiguous: {label}")
    cells = [Decimal(cell.replace(",", "")) for cell in matches[0][1:]
             if NUMERIC.fullmatch(cell)]
    if len(cells) < 3:
        raise ValueError(f"JPM firmwide row has too few numeric columns: {label}")
    return cells[:3]


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "JPM"
            or packet.get("cik") != "0000019617"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected JPM packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    event_prior = {}
    for role, source_id, quarter, current, prior, filed_at in (
        ("baseline", "HOLDOUT-JPM-BASELINE-v1", "Q2", "2Q25", "1Q25", "2025-07-15"),
        ("event", "HOLDOUT-JPM-EVENT-v1", "Q3", "3Q25", "2Q25", "2025-10-14"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{'06-30' if quarter == 'Q2' else '09-30'}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"JPM filing/source differs: {role}")
        source_path = ROOT / source["local_path"]
        lines = extract_lines(source_path)
        if not any("non-GAAP" in line and "managed basis" in line for line in lines):
            raise ValueError(f"JPM managed-basis non-GAAP source note missing: {role}")
        rows = extract_rows(source_path)
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"JPM selected metric set differs: {role}")
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, source_row, unit = EXPECTED[metric]
            expected = Decimal(str(q2 if quarter == "Q2" else q3))
            if (fact["id"] != f"JPM-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["source_row"] != source_row or fact["unit"] != unit
                    or fact["locator"] != f"Firmwide Results for JPM / {current} current column"):
                raise ValueError(f"JPM selected fact definition differs: {fact['id']}")
            current_value, previous_value, _ = _firmwide_cells(rows, source_row, current, prior)
            if current_value != expected:
                raise ValueError(f"JPM SEC firmwide row differs: {fact['id']}")
            values[metric] = current_value
            if role == "event":
                event_prior[metric] = previous_value
        selected[role] = values
    if event_prior != selected["baseline"]:
        raise ValueError("JPM Q3 Q2 comparator differs from Q2 release")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "gaap_reported_net_revenue": 1515,
        "non_gaap_managed_net_revenue": 1440,
        "gaap_noninterest_expense": 502,
        "gaap_provision_for_credit_losses": 554,
        "gaap_net_income": -594,
        "gaap_diluted_eps": Decimal("-0.17"),
    }:
        raise ValueError("JPM selected Q3-minus-Q2 changes differ")
    return {"status": "jpm_firmwide_source_rows_and_q2_comparators_match",
            "selected_facts": 12, "q2_cross_filing_comparators": 6,
            "reported_revenue_delta_usd_million": 1515,
            "net_income_delta_usd_million": -594, "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
