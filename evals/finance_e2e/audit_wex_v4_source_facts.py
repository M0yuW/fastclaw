#!/usr/bin/env python3
"""Audit WEX selected Q2/Q3 SEC cells and displayed-value rounding.

Only public source facts and arithmetic are checked. No answer or model call
is assessed here, and a displayed accounting residual is not forced to zero.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path

import rank_postcorrection_holdout_v2 as prior


HERE = Path(__file__).parent
PACKET = HERE / "wex_v4_source_fact_packet.json"
SELECTION = HERE / "postcorrection_v4_wex_replacement_pair.json"
FROZEN = HERE / "results/2026-10-24-postcorrection-v4-wex-exhibits"
MANIFEST = FROZEN / "manifest.json"
NUMBER = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")

GAAP_ROWS = {
    "payment_processing_revenue": ("Payment processing revenue", 0),
    "account_servicing_revenue": ("Account servicing revenue", 0),
    "finance_fee_revenue": ("Finance fee revenue", 0),
    "other_revenue": ("Other revenue", 0),
    "total_revenues": ("Total revenues", 0),
    "provision_for_credit_losses": ("Provision for credit losses", 0),
    "total_cost_of_services": ("Total cost of services", 0),
    "general_and_administrative": ("General and administrative", 0),
    "sales_and_marketing": ("Sales and marketing", 0),
    "operating_depreciation_amortization": ("Depreciation and amortization", 1),
    "operating_income": ("Operating income", 0),
    "financing_interest_expense_signed":
        ("Financing interest expense, net of financial instruments", 0),
    "contingent_consideration_fair_value_signed":
        ("Change in fair value of contingent consideration", 0),
    "income_before_taxes": ("Income before income taxes", 0),
    "income_tax_expense": ("Income tax expense", 0),
    "gaap_net_income": ("Net income", 0),
    "gaap_diluted_eps": ("Diluted", 0),
}


class SourceHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag == "tr":
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        self.text_parts.append(data)
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


def displayed_number(cell: str) -> Decimal:
    if not NUMBER.fullmatch(cell):
        raise ValueError(f"not a source number: {cell!r}")
    value = cell.replace(",", "")
    if value.startswith("(") and value.endswith(")"):
        value = "-" + value[1:-1]
    return Decimal(value)


def first_current_quarter(rows: list[list[str]], label: str,
                          occurrence: int = 0) -> Decimal:
    candidates = [row for row in rows if row and row[0] == label]
    if len(candidates) <= occurrence:
        raise ValueError(f"source row missing: {label} occurrence {occurrence}")
    numeric_cells = [cell for cell in candidates[occurrence][1:]
                     if NUMBER.fullmatch(cell)]
    if len(numeric_cells) < 2:
        raise ValueError(f"source row missing comparative columns: {label}")
    return displayed_number(numeric_cells[0])


def residuals(facts: dict[str, Decimal]) -> dict[str, Decimal]:
    get = facts.__getitem__
    return {
        "revenue_components_to_total": get("total_revenues") - sum(
            (get(metric) for metric in (
                "payment_processing_revenue", "account_servicing_revenue",
                "finance_fee_revenue", "other_revenue")), Decimal(0)),
        "revenues_less_expenses_to_operating": get("operating_income") - (
            get("total_revenues") - sum((get(metric) for metric in (
                "total_cost_of_services", "general_and_administrative",
                "sales_and_marketing", "operating_depreciation_amortization")),
                Decimal(0))),
        "operating_to_pretax": get("income_before_taxes") - (
            get("operating_income") + get("financing_interest_expense_signed")
            + get("contingent_consideration_fair_value_signed")
            + get("foreign_currency_gain_loss_signed")),
        "pretax_less_tax_to_net": get("gaap_net_income") - (
            get("income_before_taxes") - get("income_tax_expense")),
    }


def audit(packet: dict | None = None) -> dict:
    packet = packet or json.loads(PACKET.read_text())
    selected = json.loads(SELECTION.read_text())
    manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 4 or packet.get("paid_calls_authorized") is not False
            or selected.get("symbol") != "WEX" or len(manifest["entries"]) != 2):
        raise ValueError("unexpected packet, source selection or manifest")
    if hashlib.sha256(SELECTION.read_bytes()).hexdigest() != manifest["selection_sha256"]:
        raise ValueError("WEX source selection hash differs")
    if "WEX" in (set(prior.preflight()["selected_cik"])
                 | prior.observed_v1_symbols()):
        raise ValueError("WEX overlaps a prior observed issuer")

    all_residuals = {}
    for role in ("baseline", "event"):
        section = packet[role]
        chosen = selected[role]
        entry = next(x for x in manifest["entries"] if x["role"] == role)
        expected_path = FROZEN / f"HOLDOUT-V4-WEX-{role.upper()}.htm"
        digest = hashlib.sha256(expected_path.read_bytes()).hexdigest()
        if (digest != entry["sha256"] or digest != section["source_sha256"]
                or entry["id"] != section["source_id"]
                or entry["url"] != chosen["url"]
                or section["period"] != chosen["period"]):
            raise ValueError(f"{role} source identity differs")
        parsed = SourceHTML()
        parsed.feed(expected_path.read_text(errors="replace"))
        month = "June" if role == "baseline" else "September"
        quarter = "Second" if role == "baseline" else "Third"
        if (f"Reports {quarter} Quarter 2025 Financial Results" not in parsed.text
                or f"Three months ended {month} 30," not in parsed.text
                or "(in millions, except per share data) (unaudited)" not in parsed.text):
            raise ValueError(f"{role} period or unit header differs")
        statement_rows = parsed.rows[:42]
        if (f"Three months ended {month} 30," not in " ".join(statement_rows[1])
                or statement_rows[2].count("2025") != 2):
            raise ValueError(f"{role} source statement column basis differs")
        facts = {metric: Decimal(value) for metric, value in section["facts"].items()}
        if set(facts) != set(GAAP_ROWS) | {
                "foreign_currency_gain_loss_signed", "non_gaap_adjusted_net_income",
                "reported_total_volume_usd_billion"}:
            raise ValueError(f"{role} selected fact set differs")
        for metric, (label, occurrence) in GAAP_ROWS.items():
            observed = first_current_quarter(statement_rows, label, occurrence)
            if observed != facts[metric]:
                raise ValueError(f"{role} selected source value differs: {metric}")
        fx_labels = ("Net foreign currency gain (loss)",
                     "Net foreign currency (loss) gain")
        fx_rows = [row for row in statement_rows if row and row[0] in fx_labels]
        if len(fx_rows) != 1 or displayed_number(next(
                cell for cell in fx_rows[0][1:] if NUMBER.fullmatch(cell))) != facts[
                    "foreign_currency_gain_loss_signed"]:
            raise ValueError(f"{role} selected source value differs: foreign currency")
        adjusted = first_current_quarter(parsed.rows[150:200],
                                         "Adjusted net income")
        if adjusted != facts["non_gaap_adjusted_net_income"] or not re.search(
                r"adjusted net income.{0,80}non-GAAP measure", parsed.text,
                re.IGNORECASE):
            raise ValueError(f"{role} non-GAAP adjusted net income differs")
        volume = re.search(r"Total volume across all segments was \$([\d.]+) billion",
                           parsed.text)
        if (not volume or Decimal(volume.group(1)) != facts[
                "reported_total_volume_usd_billion"]):
            raise ValueError(f"{role} reported volume differs")
        guidance = re.search(
            r"Company now expects revenue in the range of \$([\d.]+) billion"
            r" to \$([\d.]+) billion.{0,220}?Adjusted net income is now"
            r" expected to be in the range of \$([\d.]+) to \$([\d.]+)"
            r" per diluted share", parsed.text)
        if (not guidance or list(guidance.groups()[:2]) != section["guidance"][
                "full_year_revenue_usd_billion_range"]
                or list(guidance.groups()[2:]) != section["guidance"][
                    "full_year_adjusted_net_income_per_share_range"]):
            raise ValueError(f"{role} forward-looking guidance differs")
        values = residuals(facts)
        if any(abs(value) > Decimal("0.11") for value in values.values()):
            raise ValueError(f"{role} displayed GAAP bridge exceeds rounding tolerance")
        all_residuals[role] = {k: str(v) for k, v in values.items()}
    return {
        "status": "wex_selected_source_facts_and_rounding_audited",
        "selected_facts": sum(len(packet[role]["facts"]) for role in ("baseline", "event")),
        "displayed_gaap_residuals_usd_million": all_residuals,
        "eligible_source_pair_subject_to_panel_freeze": True,
        "model_observations": 0,
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
