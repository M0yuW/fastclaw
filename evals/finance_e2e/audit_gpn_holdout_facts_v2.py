#!/usr/bin/env python3
"""Audit GPN current-quarter GAAP/disposition bridge against frozen SEC exhibits."""

from __future__ import annotations

import json
import re

from fetch_sources import ROOT, verify_local_lock
from sec_html_rows import extract_rows


PACKET = ROOT / "gpn_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\)")
EXPECTED = {
    "gaap_revenues": (1956747, 2007637, "REV", "Revenues", "statement"),
    "gaap_cost_of_service": (498788, 556682, "COST", "Cost of service", "statement"),
    "gaap_selling_general_administrative":
        (1031020, 1016832, "SGA", "Selling, general and administrative", "statement"),
    "gaap_disposition_gain_as_negative_expense":
        (-267, -343891, "DISP", ("Gain on business disposition",
                                   "Gain on business dispositions"), "statement"),
    "gaap_operating_income": (427206, 778014, "OPINC", "Operating income", "statement"),
    "gaap_income_continuing_operations":
        (212095, 473275, "CONT", "Income from continuing operations", "statement"),
    "gaap_income_discontinued_operations":
        (34003, 187320, "DISCONT", "Income from discontinued operations, net of tax", "statement"),
    "gaap_net_income": (246098, 660595, "NET", "Net income", "statement"),
    "gaap_net_income_attributable_to_noncontrolling_interests_signed":
        (-4458, -25386, "NCI",
         "Net income attributable to noncontrolling interests, net of income tax", "statement"),
    "gaap_net_income_attributable_to_global_payments":
        (241640, 635209, "ATTR", "Net income attributable to Global Payments", "statement"),
    "non_gaap_adjusted_operating_income":
        (1052749, 1092829, "ADJOP", "Adjusted operating income", "adjusted"),
}


def _signed(cell: str) -> int:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not a signed GPN financial cell: {cell!r}")
    raw = cell.replace(",", "")
    if raw.startswith("("):
        raw = "-" + raw[1:-1]
    return int(raw)


def _current_cell(rows: list[list[str]], source_row: str, section: str,
                  quarter_end: str) -> int:
    if len(rows) < 40 or rows[3][1] != "Three Months Ended" or rows[4][1] != quarter_end:
        raise ValueError("GPN standalone-quarter statement header differs")
    if rows[5][1] != "2025":
        raise ValueError("GPN statement current-year column differs")
    if section == "statement":
        candidates = rows[6:33]
    else:
        if rows[33][1] != "Three Months Ended" or rows[34][1] != quarter_end or rows[35][1] != "2025":
            raise ValueError("GPN adjusted standalone-quarter header differs")
        candidates = rows[36:40]
    matches = [row for row in candidates if row and row[0] == source_row]
    if len(matches) != 1:
        raise ValueError(f"GPN source row missing/ambiguous: {source_row}")
    numbers = [cell for cell in matches[0][1:] if NUMBER.fullmatch(cell)]
    if len(numbers) < 2:
        raise ValueError(f"GPN row lacks a comparison column: {source_row}")
    return _signed(numbers[0])


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "GPN"
            or packet.get("cik") != "0001123360"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected GPN packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, month, end, filed_at in (
        ("baseline", "HOLDOUT-GPN-BASELINE-v1", "Q2", "06-30", "June 30,", "2025-08-06"),
        ("event", "HOLDOUT-GPN-EVENT-v1", "Q3", "09-30", "September 30,", "2025-11-04"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{month}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"GPN filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"GPN selected metric set differs: {role}")
        source_path = ROOT / source["local_path"]
        html = source_path.read_text(encoding="utf-8", errors="replace")
        if ("(In thousands, except per share data)" not in html
                or "Adjusted operating income reflects total company performance, including discontinued operations." not in html):
            raise ValueError(f"GPN source unit or adjusted-measure scope differs: {role}")
        rows = extract_rows(source_path)
        values = {}
        for fact in facts:
            metric = fact["metric"]
            q2, q3, suffix, labels, kind = EXPECTED[metric]
            expected = q2 if quarter == "Q2" else q3
            source_row = labels[0 if quarter == "Q2" else 1] if isinstance(labels, tuple) else labels
            locator = (f"{'Condensed consolidated statement' if kind == 'statement' else 'Adjusted results summary'} "
                       f"/ Three Months Ended {end} 2025")
            if (fact["id"] != f"GPN-{quarter}-{suffix}" or fact["value"] != expected
                    or fact["unit"] != "USD_thousand_reported"
                    or fact["source_row"] != source_row or fact["locator"] != locator):
                raise ValueError(f"GPN selected fact definition differs: {fact['id']}")
            if _current_cell(rows, source_row, kind, end) != expected:
                raise ValueError(f"GPN SEC current-quarter row differs: {fact['id']}")
            values[metric] = expected
        selected[role] = values
    for role, values in selected.items():
        if (values["gaap_revenues"] - values["gaap_cost_of_service"]
                - values["gaap_selling_general_administrative"]
                - values["gaap_disposition_gain_as_negative_expense"]
                != values["gaap_operating_income"]):
            raise ValueError(f"GPN operating-income bridge differs: {role}")
        if (values["gaap_income_continuing_operations"]
                + values["gaap_income_discontinued_operations"]
                != values["gaap_net_income"]):
            raise ValueError(f"GPN continuing/discontinued bridge differs: {role}")
        if (values["gaap_net_income"]
                + values["gaap_net_income_attributable_to_noncontrolling_interests_signed"]
                != values["gaap_net_income_attributable_to_global_payments"]):
            raise ValueError(f"GPN attributable-income bridge differs: {role}")
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if (delta["gaap_revenues"] != 50890
            or delta["gaap_operating_income"] != 350808
            or delta["gaap_disposition_gain_as_negative_expense"] != -343624
            or delta["non_gaap_adjusted_operating_income"] != 40080
            or delta["gaap_net_income_attributable_to_global_payments"] != 393569
            or delta["gaap_income_discontinued_operations"] != 153317
            or delta["gaap_operating_income"]
            + delta["gaap_disposition_gain_as_negative_expense"] != 7184):
        raise ValueError("GPN selected Q3-minus-Q2 changes differ")
    return {"status": "gpn_gaap_disposition_and_adjusted_basis_separated",
            "selected_facts": 22, "gaap_operating_delta_usd_thousand": 350808,
            "disposition_gain_delta_usd_thousand": 343624,
            "non_gaap_adjusted_operating_delta_usd_thousand": 40080,
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
