#!/usr/bin/env python3
"""Audit State Street selected rows and Q3's Q2 comparator against locked SEC bytes."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "stt_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMERIC = re.compile(r"\d[\d,]*")
EXPECTED = {
    "gaap_total_fee_revenue": (2719, 2829, "FEE", "Total fee revenue"),
    "gaap_net_interest_income": (729, 715, "NII", "Net interest income"),
    "gaap_total_revenue": (3448, 3545, "REV", "Total revenue"),
    "gaap_provision_for_credit_losses": (30, 9, "PROV", "Provision for credit losses"),
    "gaap_total_expenses": (2529, 2434, "EXP", "Total expenses"),
    "gaap_net_income": (693, 861, "NET", "Net income"),
}


def _summary_cells(rows: list[list[str]], label: str, current: str, prior: str) -> list[int]:
    headers = [row for row in rows[:20] if row and "Table presents summary results" in row[0]]
    if len(headers) != 1 or current not in " ".join(headers[0]) or prior not in " ".join(headers[0]):
        raise ValueError("State Street summary quarter header differs")
    matches = [row for row in rows[:20] if row and row[0] == label]
    if len(matches) != 1:
        raise ValueError(f"State Street summary row missing or ambiguous: {label}")
    values = [int(cell.replace(",", "")) for cell in matches[0][1:]
              if NUMERIC.fullmatch(cell)]
    if len(values) < 3:
        raise ValueError(f"State Street summary has too few columns: {label}")
    return values[:3]


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "STT"
            or packet.get("cik") != "0000093751"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected State Street packet identity")
    locks = {entry["id"]: entry for entry in lock["entries"]}
    discoveries = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    comparators = {}
    event_rows = None
    for role, source_id, current, prior, period, filed_at in (
        ("baseline", "HOLDOUT-STT-BASELINE-v1", "2Q25", "1Q25",
         "CY2025 Q2 ended 2025-06-30", "2025-07-15"),
        ("event", "HOLDOUT-STT-EVENT-v1", "3Q25", "2Q25",
         "CY2025 Q3 ended 2025-09-30", "2025-10-17"),
    ):
        section, source, discovery = packet[role], locks[source_id], discoveries[source_id]
        if (section["period"] != period or section["as_of"] != filed_at
                or discovery["filed_at"] != filed_at or discovery["form"] != "8-K"
                or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"State Street filing/source differs: {role}")
        rows = extract_rows(ROOT / source["local_path"])
        if role == "event":
            event_rows = rows
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {f["metric"] for f in facts} != set(EXPECTED):
            raise ValueError(f"State Street selected metric set differs: {role}")
        values = {}
        for fact in facts:
            metric = fact["metric"]
            baseline_value, event_value, suffix, source_row = EXPECTED[metric]
            expected = baseline_value if role == "baseline" else event_value
            quarter = "Q2" if role == "baseline" else "Q3"
            if (fact["id"] != f"STT-{quarter}-{suffix}"
                    or fact["source_row"] != source_row
                    or fact["unit"] != "USD_million_rounded"
                    or fact["value"] != expected):
                raise ValueError(f"State Street selected definition differs: {fact['id']}")
            current_value, prior_value, _ = _summary_cells(rows, source_row, current, prior)
            if current_value != fact["value"]:
                raise ValueError(f"State Street selected SEC row differs: {fact['id']}")
            values[metric] = current_value
            if role == "event":
                comparators[metric] = prior_value
        selected[role] = values
    if comparators != selected["baseline"]:
        raise ValueError("State Street Q3 Q2 comparator differs from Q2 release")
    before, after = selected["baseline"], selected["event"]
    if (before["gaap_total_revenue"] - before["gaap_total_fee_revenue"]
            - before["gaap_net_interest_income"] != 0):
        raise ValueError("State Street Q2 selected revenue bridge differs")
    residual = (after["gaap_total_revenue"] - before["gaap_total_revenue"]
                - (after["gaap_total_fee_revenue"] - before["gaap_total_fee_revenue"])
                - (after["gaap_net_interest_income"] - before["gaap_net_interest_income"]))
    if residual != 1 or event_rows is None:
        raise ValueError("State Street revenue delta residual differs")
    other = [row for row in event_rows[:20] if row and row[0] == "Other income"]
    if len(other) != 1 or other[0][1] != "1":
        raise ValueError("State Street Q3 other-income residual source differs")
    if ((after["gaap_total_revenue"] - before["gaap_total_revenue"]) != 97
            or (after["gaap_total_expenses"] - before["gaap_total_expenses"]) != -95
            or (after["gaap_provision_for_credit_losses"]
                - before["gaap_provision_for_credit_losses"]) != -21
            or (after["gaap_net_income"] - before["gaap_net_income"]) != 168):
        raise ValueError("State Street selected deltas differ")
    return {"status": "stt_selected_sec_rows_and_q2_comparators_match",
            "selected_facts": 12, "q2_cross_filing_comparators": 6,
            "revenue_mix_unlisted_residual_usd_million": residual,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
