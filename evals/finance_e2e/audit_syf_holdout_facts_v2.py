#!/usr/bin/env python3
"""Audit SYF release-narrative cells with explicit credit-ratio denominators."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_blocks import extract_blocks


PACKET = ROOT / "syf_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
EXPECTED = {
    "reported_purchase_volume": ("PVOL", (46.1, 46.0), "USD_billion_reported",
                                  "Purchase volume", "•Purchase volume",
                                  r"Purchase volume (?:decreased|increased) \d+% to \$(\d+\.\d+) billion"),
    "reported_period_end_loan_receivables":
        ("LOANS", (99.8, 100.2), "USD_billion_reported",
         "Loan receivables", "•Loan receivables decreased",
         r"Loan receivables decreased \d+% to \$(\d+\.\d+) billion"),
    "reported_average_active_accounts":
        ("ACTIVE", (68.1, 68.3), "million_accounts_reported",
         "Average active accounts", "•Average active accounts",
         r"Average active accounts decreased \d+% to (\d+\.\d+) million"),
    "reported_net_interest_income":
        ("NII", (4.5, 4.7), "USD_billion_reported",
         "Net interest income", "•Net interest income",
         r"Net interest income increased \$\d+ million, or \d+%, to \$(\d+\.\d+) billion"),
    "reported_reserve_release":
        ("RELEASE", (265, 152), "USD_million_rounded",
         "reserve release", "•Provision for credit losses",
         r"reserve release of \$(\d+) million"),
    "reported_30_plus_delinquency_period_end_ratio":
        ("30DPD", (4.18, 4.39), "percent",
         "Loans 30+ days past due as a percentage of total period-end loan receivables",
         "•Loans 30+ days past due",
         r"Loans 30\+ days past due as a percentage of total period-end loan receivables were (\d+\.\d+)%"),
    "reported_net_charge_off_average_receivables_ratio":
        ("NCO", (5.70, 5.16), "percent",
         "Net charge-offs as a percentage of total average loan receivables",
         "•Net charge-offs as a percentage",
         r"Net charge-offs as a percentage of total average loan receivables were (\d+\.\d+)%"),
    "gaap_diluted_eps":
        ("EPS", (2.50, 2.86), "USD_per_share_reported",
         "per diluted share", "STAMFORD, Conn",
         r"2025 net earnings of \$[\d.]+ (?:million|billion), or \$(\d+\.\d+) per diluted share"),
}


def _source_number(blocks: list[str], prefix: str, pattern: str) -> Decimal:
    candidates = [block for block in blocks if block.startswith(prefix)]
    if len(candidates) != 1:
        raise ValueError(f"SYF narrative block missing/ambiguous: {prefix}")
    match = re.search(pattern, candidates[0])
    if match is None:
        raise ValueError(f"SYF metric or denominator differs: {prefix}")
    return Decimal(match.group(1))


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "SYF"
            or packet.get("cik") != "0001601712"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected SYF packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, end, filed_at, label in (
        ("baseline", "HOLDOUT-SYF-BASELINE-v1", "Q2", "06-30", "2025-07-22", "Second"),
        ("event", "HOLDOUT-SYF-EVENT-v1", "Q3", "09-30", "2025-10-15", "Third"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{end}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"SYF filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"SYF selected metric set differs: {role}")
        blocks = extract_blocks(ROOT / source["local_path"])
        if not any(f"{label.lower()} quarter 2025 net earnings" in block.lower()
                   for block in blocks):
            raise ValueError(f"SYF fiscal quarter narrative differs: {role}")
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, row, prefix, pattern = EXPECTED[metric]
            expected = Decimal(str(pair[0 if quarter == "Q2" else 1]))
            if (fact["id"] != f"SYF-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != row
                    or fact["locator"] != f"{label}-quarter release / current quarter narrative"):
                raise ValueError(f"SYF selected fact definition differs: {fact['id']}")
            actual = _source_number(blocks, prefix, pattern)
            if actual != expected:
                raise ValueError(f"SYF SEC current-quarter narrative differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "reported_purchase_volume": Decimal("-0.1"),
        "reported_period_end_loan_receivables": Decimal("0.4"),
        "reported_average_active_accounts": Decimal("0.2"),
        "reported_net_interest_income": Decimal("0.2"),
        "reported_reserve_release": Decimal("-113"),
        "reported_30_plus_delinquency_period_end_ratio": Decimal("0.21"),
        "reported_net_charge_off_average_receivables_ratio": Decimal("-0.54"),
        "gaap_diluted_eps": Decimal("0.36"),
    }:
        raise ValueError("SYF selected Q3-minus-Q2 changes differ")
    return {"status": "syf_narrative_rates_and_rounded_levels_match",
            "selected_facts": 16, "delinquency_change_percentage_points": "0.21",
            "charge_off_change_percentage_points": "-0.54",
            "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
