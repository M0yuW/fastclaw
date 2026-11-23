#!/usr/bin/env python3
"""Audit richer PAYO Q2/Q3 facts, guidance, and GAAP bridges against SEC bytes.

Non-GAAP and management statements are typed separately. This checks source
selection and arithmetic, not the truth of management's causal explanation or
the quality of any future model answer.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

from fetch_sources import ROOT
from sec_html_rows import extract_rows


HERE = Path(__file__).parent
PACKET = HERE / "payo_v4_rich_fact_packet.json"
PAIR_SELECTION = HERE / "postcorrection_v4_first4_sec_pairs.json"
LOCK = HERE / "results/2026-10-24-postcorrection-v4-first4-exhibits-complete/manifest.json"
NUMERIC = re.compile(r"\(?\d[\d,]*(?:\.\d+)?\)?")

# Metric, source-table kind, exact first-column row label, value pair, unit, class.
ROWS = {
    "gaap_revenues": ("statement", "Revenues", (260614, 270850), "USD_thousand_reported", "historical_gaap"),
    "gaap_total_operating_expenses": ("statement", "Total operating expenses", (230537, 234503), "USD_thousand_reported", "historical_gaap"),
    "gaap_operating_income": ("statement", "Operating income", (30077, 36347), "USD_thousand_reported", "historical_gaap"),
    "gaap_financial_income_expense_signed": ("statement", ("Financial income (expense), net", "Financial expense, net"), (-227, -5836), "USD_thousand_reported", "historical_gaap"),
    "gaap_income_before_taxes": ("statement", "Income before income taxes", (29850, 30511), "USD_thousand_reported", "historical_gaap"),
    "gaap_tax_expense_magnitude": ("statement", ("Income taxes", "Tax benefit (expense) on income"), (10370, 16388), "USD_thousand_reported", "historical_gaap"),
    "gaap_net_income": ("statement", "Net income", (19480, 14123), "USD_thousand_reported", "historical_gaap"),
    "non_gaap_adjusted_ebitda": ("adjusted", "Adjusted EBITDA", (66425, 71267), "USD_thousand_reported", "historical_non_gaap"),
    "reported_revenue_ex_interest_income": ("headline", "Revenue ex. interest income", ("202.3", "211.4"), "USD_million_displayed", "operating_headline"),
    "reported_interest_income": ("headline", "Interest income", ("58.3", "59.5"), "USD_million_displayed", "operating_headline"),
    "reported_volume": ("headline", "Volume ($bn)", ("20.7", "22.3"), "USD_billion_displayed", "operating_metric"),
    "reported_active_ideal_customer_profiles": ("headline", "Active Ideal Customer Profiles", (559, 548), "thousand_customers_displayed", "operating_metric"),
    "reported_total_take_rate": ("headline", "Revenue as a % of volume", (126, 121), "basis_points", "operating_metric"),
    "reported_smb_take_rate": ("headline", "SMB customer take rate", (120, 121), "basis_points", "operating_metric"),
    "reported_transaction_cost_ratio": ("headline", "Transaction costs as a % of revenue", ("15.6", "15.7"), "percent", "operating_metric"),
}
SUFFIX = {
    "gaap_revenues": "REV", "gaap_total_operating_expenses": "OPEX",
    "gaap_operating_income": "OPINC",
    "gaap_financial_income_expense_signed": "FIN",
    "gaap_income_before_taxes": "PRETAX",
    "gaap_tax_expense_magnitude": "TAX", "gaap_net_income": "NET",
    "non_gaap_adjusted_ebitda": "ADJEBITDA",
    "reported_revenue_ex_interest_income": "REVEXINT",
    "reported_interest_income": "INT", "reported_volume": "VOL",
    "reported_active_ideal_customer_profiles": "ICP",
    "reported_total_take_rate": "TAKE",
    "reported_smb_take_rate": "SMBTAKE",
    "reported_transaction_cost_ratio": "TXCOSTR",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def numeric(cell: str) -> Decimal:
    found = NUMERIC.search(cell)
    if found is None:
        raise ValueError(f"numeric source cell missing: {cell!r}")
    token = found.group().replace(",", "")
    return -Decimal(token[1:-1]) if token.startswith("(") else Decimal(token)


def selected_row(rows: list[list[str]], label: str, kind: str) -> list[str]:
    span = {"headline": (0, 15), "statement": (30, 80),
            "adjusted": (100, 120)}[kind]
    candidates = [row for row in rows[span[0]:span[1]] if row and
                  (row[0] == label if kind != "headline" else row[0].startswith(label))]
    if len(candidates) != 1:
        raise ValueError(f"ambiguous/missing {kind} source row: {label}")
    return candidates[0]


def row_value(rows: list[list[str]], label: str, kind: str,
              metric: str, role: str) -> Decimal:
    row = selected_row(rows, label, kind)
    if kind == "headline":
        return numeric(row[9])
    values = [numeric(cell) for cell in row[1:] if NUMERIC.fullmatch(cell.replace("$", "").strip())]
    if not values:
        raise ValueError(f"source row has no numeric value: {label}")
    value = values[0]
    if metric == "gaap_tax_expense_magnitude":
        if (role == "baseline" and value <= 0) or (role == "event" and value >= 0):
            raise ValueError("PAYO source tax sign changed")
        return abs(value)
    return value


def guidance(rows: list[list[str]]) -> dict:
    output = {}
    for label, key in (("Revenue", "revenue_usd_million_range"),
                       ("Adjusted EBITDA1", "adjusted_ebitda_usd_million_range"),
                       ("Transaction costs", "transaction_cost_percent_approx")):
        matches = [row for row in rows[20:31] if len(row) > 3 and row[2] == label]
        if len(matches) != 1:
            raise ValueError(f"guidance row missing/ambiguous: {label}")
        values = [Decimal(item.replace(",", ""))
                  for item in NUMERIC.findall(matches[0][3])]
        if key.endswith("_range"):
            if len(values) != 2:
                raise ValueError(f"guidance range differs: {label}")
            output[key] = values
        else:
            if len(values) != 1:
                raise ValueError("transaction guidance differs")
            output[key] = values[0]
    return output


def audit(packet: dict | None = None, manifest: dict | None = None) -> dict:
    packet = packet or json.loads(PACKET.read_text())
    manifest = manifest or json.loads(LOCK.read_text())
    if (packet.get("symbol") != "PAYO" or packet.get("cik") != "0001845815"
            or packet.get("version") != 4 or len(ROWS) != 15):
        raise ValueError("unexpected PAYO packet identity or metric set")
    if manifest["selection_sha256"] != file_hash(PAIR_SELECTION):
        raise ValueError("pair selection differs from exhibit lock")
    entries = {entry["id"]: entry for entry in manifest["entries"]}
    checked = {}
    source_rows = {}
    for index, role in enumerate(("baseline", "event")):
        section = packet[role]
        entry = entries[f"HOLDOUT-V4-PAYO-{role.upper()}"]
        path = ROOT / entry["local_path"]
        if (not path.is_file() or file_hash(path) != entry["sha256"]
                or section["source_sha256"] != entry["sha256"]
                or section["source_url"] != entry["url"]
                or section["period"] != entry["period"]
                or section["filed_at"] != entry["filed_at"]):
            raise ValueError(f"PAYO frozen source identity differs: {role}")
        rows = extract_rows(path)
        source_rows[role] = rows
        expected_header = "2Q 2025" if role == "baseline" else "3Q 2025"
        if expected_header not in rows[2] or expected_header not in path.read_text(errors="replace"):
            raise ValueError(f"PAYO financial highlights period header differs: {role}")
        if "non-GAAP financial measure" not in path.read_text(errors="replace"):
            raise ValueError(f"PAYO non-GAAP measure definition absent: {role}")
        facts = {f["metric"]: f for f in section["facts"]}
        if len(section["facts"]) != len(ROWS) or set(facts) != set(ROWS):
            raise ValueError(f"PAYO metric inventory differs: {role}")
        values = {}
        for metric, (kind, source_labels, expected_pair, unit, fact_kind) in ROWS.items():
            label = source_labels[index] if isinstance(source_labels, tuple) else source_labels
            fact = facts[metric]
            expected_id = f"PAYO-{'Q2' if role == 'baseline' else 'Q3'}-{SUFFIX[metric]}"
            row_label_matches = (fact["source_row"] == label or
                                 (kind == "headline" and fact["source_row"].startswith(label)))
            if (fact["id"] != expected_id or not row_label_matches
                    or fact["kind"] != fact_kind or fact["unit"] != unit):
                raise ValueError(f"PAYO fact definition differs: {fact['id']}")
            actual = row_value(rows, label, kind, metric, role)
            expected = Decimal(str(expected_pair[index]))
            if actual != expected or Decimal(str(fact["value"])) != expected:
                raise ValueError(f"PAYO selected source value differs: {fact['id']}: {actual} vs {expected}")
            values[metric] = actual
            if role == "event" and kind == "headline":
                previous = numeric(selected_row(rows, label, kind)[7])
                baseline = Decimal(str(expected_pair[0]))
                if previous != baseline:
                    raise ValueError(f"Q3 exhibit Q2 comparator differs: {metric}")
        reported_guidance = guidance(rows)
        for key, value in reported_guidance.items():
            stated = section["guidance"][key]
            if isinstance(value, list):
                if [Decimal(str(item)) for item in stated] != value:
                    raise ValueError(f"PAYO guidance differs: {role} {key}")
            elif Decimal(str(stated)) != value:
                raise ValueError(f"PAYO guidance differs: {role} {key}")
        if section["guidance"]["status"] != "company_forward_looking_guidance_not_realized":
            raise ValueError("guidance kind differs")
        if values["gaap_revenues"] - values["gaap_total_operating_expenses"] != values["gaap_operating_income"]:
            raise ValueError(f"PAYO operating-income bridge differs: {role}")
        if values["gaap_operating_income"] + values["gaap_financial_income_expense_signed"] != values["gaap_income_before_taxes"]:
            raise ValueError(f"PAYO pre-tax bridge differs: {role}")
        if values["gaap_income_before_taxes"] - values["gaap_tax_expense_magnitude"] != values["gaap_net_income"]:
            raise ValueError(f"PAYO net-income bridge differs: {role}")
        checked[role] = values
    statements = packet.get("attributed_management_statements") or []
    if len(statements) != 3 or any(item.get("basis") != "management_statement_not_independently_proven"
                                   for item in statements):
        raise ValueError("PAYO attributed management-statement inventory differs")
    expected_statements = (
        ("CY2025 Q2", "Company attributes year-over-year revenue excluding interest income growth partly to volume growth and SMB take-rate expansion."),
        ("CY2025 Q3", "Company attributes year-over-year revenue excluding interest income growth partly to volume growth and SMB take-rate expansion."),
        ("CY2025 Q3", "Company says higher customer funds partly offset the effect of lower rates on interest income."),
    )
    if tuple((item.get("period"), item.get("claim")) for item in statements) != expected_statements:
        raise ValueError("PAYO attributed management claim differs")
    for role, index, required in (
        ("baseline", 17, ("16% year-over-year", "11% volume growth", "take rate expansion")),
        ("event", 17, ("15% year-over-year", "9% volume growth", "take rate expansion")),
        ("event", 24, ("Customer fund growth", "lower interest rates")),
    ):
        text = " ".join(source_rows[role][index])
        if not all(phrase in text for phrase in required):
            raise ValueError(f"PAYO management disclosure differs: {role} row {index}")
    before, after = checked["baseline"], checked["event"]
    deltas = {metric: after[metric] - before[metric] for metric in ROWS}
    if (deltas["gaap_revenues"] != 10236 or deltas["gaap_operating_income"] != 6270
            or deltas["gaap_financial_income_expense_signed"] != -5609
            or deltas["gaap_income_before_taxes"] != 661
            or deltas["gaap_tax_expense_magnitude"] != 6018
            or deltas["gaap_net_income"] != -5357):
        raise ValueError("PAYO selected GAAP change bridge differs")
    return {"status": "payo_rich_gaap_operating_guidance_source_audit_pass",
            "selected_facts": 30, "cross_filing_headline_comparators": 7,
            "guidance_fields": 6, "gaap_net_income_delta_usd_thousand": "-5357",
            "model_observations": 0}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
