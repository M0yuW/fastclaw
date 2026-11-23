#!/usr/bin/env python3
"""Audit COF release facts with Discover-scope and reserve/charge-off separation."""

from __future__ import annotations

import json
import re
from decimal import Decimal

from fetch_sources import ROOT, verify_local_lock
from sec_html_blocks import extract_blocks
from sec_html_rows import extract_rows


PACKET = ROOT / "cof_holdout_fact_packet_v2.json"
MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
EXPECTED = {
    "reported_total_net_revenue": ("REV", (12.5, 15.4), "USD_billion_reported",
                                   "Total net revenue", "summary", "•Total net revenue",
                                   r"Total net revenue increased \d+ percent to \$(\d+\.\d+) billion"),
    "reported_total_noninterest_expense":
        ("EXP", (7.0, 8.3), "USD_billion_reported", "Total non-interest expense",
         "summary", "•Total non-interest expense",
         r"Total non-interest expense increased \d+ percent to \$(\d+\.\d+) billion"),
    "reported_preprovision_earnings":
        ("PPNR", (5.5, 7.1), "USD_billion_reported", "Pre-provision earnings",
         "summary", "•Pre-provision earnings",
         r"Pre-provision earnings\(2\) increased \d+ percent to \$(\d+\.\d+) billion"),
    "reported_provision_for_credit_losses":
        ("PROV", (11.4, 2.7), "USD_billion_reported", "Provision for credit losses",
         "summary", "•Provision for credit losses",
         r"Provision for credit losses (?:increased|decreased) \$[\d.]+ billion to \$(\d+\.\d+) billion"),
    "reported_net_charge_offs":
        ("NCO", (3.1, 3.5), "USD_billion_reported", "Net charge-offs",
         "summary", "◦Net charge-offs",
         r"Net charge-offs of \$(\d+\.\d+) billion"),
    "reported_signed_loan_reserve_movement":
        ("RESERVE", (7.9, -0.760), "USD_billion_reported",
         ("loan reserve build", "loan reserve release"), "summary",
         ("◦$7.9 billion loan reserve build", "◦$760 million loan reserve release"),
         (r"\$(\d+\.\d+) billion loan reserve build", r"\$(\d+) million loan reserve release")),
    "reported_signed_net_income":
        ("NET", (-4.3, 3.2), "USD_billion_reported", ("net loss", "net income"),
         "announcement", "McLean, Va.",
         (r"announced net loss for the second quarter of 2025 of \$(\d+\.\d+) billion",
          r"announced net income for the third quarter of 2025 of \$(\d+\.\d+) billion")),
    "gaap_diluted_eps":
        ("EPS", (-8.58, 4.83), "USD_per_share_reported", "per diluted common share",
         "announcement", "McLean, Va.",
         (r"or \$\((\d+\.\d+)\) per diluted common share",
          r"or \$(\d+\.\d+) per diluted common share")),
    "non_gaap_adjusted_diluted_eps":
        ("ADJEPS", (5.48, 5.95), "USD_per_share_reported", "Adjusted net income",
         "adjusted announcement", "McLean, Va.",
         (r"Adjusted net income\(1\) for the second quarter of 2025 was \$(\d+\.\d+) per diluted common share",
          r"Adjusted net income\(1\) for the third quarter of 2025 was \$(\d+\.\d+) per diluted common share")),
    "reported_period_end_loans_held_for_investment":
        ("LOANS", (439.3, 443.2), "USD_billion_reported",
         "Period-end loans held for investment", "summary",
         "•Period-end loans held for investment",
         r"Period-end loans held for investment in the quarter increased \$[\d.]+ billion, or [\w ]+ percent, to \$(\d+\.\d+) billion"),
    "reported_cet1_standardized_ratio":
        ("CET1", (14.0, 14.4), "percent", "Common equity Tier 1 capital ratio",
         "summary", "•Common equity Tier 1 capital ratio",
         r"Common equity Tier 1 capital ratio\(3\) under Basel III Standardized Approach of (\d+\.\d+) percent"),
}


def _source_number(blocks: list[str], prefix: str, pattern: str) -> Decimal:
    candidates = [block for block in blocks if block.startswith(prefix)]
    if len(candidates) != 1:
        raise ValueError(f"COF source block missing/ambiguous: {prefix}")
    match = re.search(pattern, candidates[0])
    if match is None:
        raise ValueError(f"COF source measure/basis differs: {prefix}")
    return Decimal(match.group(1))


def audit(packet: dict, lock: dict, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text())
    if (packet.get("version") != 2 or packet.get("symbol") != "COF"
            or packet.get("cik") != "0000927628"
            or packet.get("workflow_eligibility") != ["sec_event_to_thesis_review"]):
        raise ValueError("unexpected COF packet identity")
    locked = {entry["id"]: entry for entry in lock["entries"]}
    discovered = {entry["id"]: entry for entry in manifest["sources"]}
    selected = {}
    for role, source_id, quarter, period_end, filed_at, label in (
        ("baseline", "HOLDOUT-COF-BASELINE-v1", "Q2", "06-30", "2025-07-22", "Second"),
        ("event", "HOLDOUT-COF-EVENT-v1", "Q3", "09-30", "2025-10-21", "Third"),
    ):
        section, source, discovery = packet[role], locked[source_id], discovered[source_id]
        if (section["period"] != f"CY2025 {quarter} ended 2025-{period_end}"
                or section["as_of"] != filed_at or discovery["filed_at"] != filed_at
                or discovery["form"] != "8-K" or discovery["document_type"] != "EX-99.1"
                or section["source_url"] != source["url"]
                or section["source_sha256"] != source["sha256"]
                or section["local_path"] != source["local_path"]):
            raise ValueError(f"COF filing/source differs: {role}")
        facts = section["facts"]
        if len(facts) != len(EXPECTED) or {fact["metric"] for fact in facts} != set(EXPECTED):
            raise ValueError(f"COF selected metric set differs: {role}")
        source_path = ROOT / source["local_path"]
        blocks = extract_blocks(source_path)
        if not any(block.startswith(f"Capital One Reports {label} Quarter 2025")
                   for block in blocks):
            raise ValueError(f"COF current-quarter announcement differs: {role}")
        if quarter == "Q2":
            if not any("completed our acquisition of Discover on May 18th" in block
                       for block in blocks):
                raise ValueError("COF Discover close/scope disclosure differs")
            rows = extract_rows(source_path)
            if (len(rows) < 6 or rows[5][0] != "Initial allowance build for Discover non-PCD loans"
                    or "8,767" not in rows[5]):
                raise ValueError("COF Q2 initial Discover allowance item differs")
        values = {}
        for fact in facts:
            metric = fact["metric"]
            suffix, pair, unit, labels, kind, prefixes, patterns = EXPECTED[metric]
            index = 0 if quarter == "Q2" else 1
            expected = Decimal(str(pair[index]))
            source_row = labels[index] if isinstance(labels, tuple) else labels
            prefix = prefixes[index] if isinstance(prefixes, tuple) else prefixes
            pattern = patterns[index] if isinstance(patterns, tuple) else patterns
            locator = f"{label}-quarter release / {'current-quarter ' if kind != 'adjusted announcement' else ''}{kind}"
            if (fact["id"] != f"COF-{quarter}-{suffix}"
                    or Decimal(str(fact["value"])) != expected
                    or fact["unit"] != unit or fact["source_row"] != source_row
                    or fact["locator"] != locator):
                raise ValueError(f"COF selected fact definition differs: {fact['id']}")
            actual = _source_number(blocks, prefix, pattern)
            if metric in ("reported_signed_net_income", "gaap_diluted_eps") and quarter == "Q2":
                actual = -actual
            if metric == "reported_signed_loan_reserve_movement" and quarter == "Q3":
                actual = -actual / Decimal(1000)
            if actual != expected:
                raise ValueError(f"COF SEC current-quarter narrative differs: {fact['id']}")
            values[metric] = actual
        selected[role] = values
    before, after = selected["baseline"], selected["event"]
    delta = {metric: after[metric] - before[metric] for metric in EXPECTED}
    if delta != {
        "reported_total_net_revenue": Decimal("2.9"),
        "reported_total_noninterest_expense": Decimal("1.3"),
        "reported_preprovision_earnings": Decimal("1.6"),
        "reported_provision_for_credit_losses": Decimal("-8.7"),
        "reported_net_charge_offs": Decimal("0.4"),
        "reported_signed_loan_reserve_movement": Decimal("-8.660"),
        "reported_signed_net_income": Decimal("7.5"),
        "gaap_diluted_eps": Decimal("13.41"),
        "non_gaap_adjusted_diluted_eps": Decimal("0.47"),
        "reported_period_end_loans_held_for_investment": Decimal("3.9"),
        "reported_cet1_standardized_ratio": Decimal("0.4"),
    }:
        raise ValueError("COF selected displayed-value Q3-minus-Q2 changes differ")
    return {"status": "cof_discover_scope_and_reserve_vs_chargeoffs_separated",
            "selected_facts": 22, "signed_reserve_delta_usd_billion": "-8.660",
            "net_chargeoffs_delta_usd_billion": "0.4", "model_observations": 0}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(audit(json.loads(PACKET.read_text()), json.loads(LOCK.read_text()),
                           json.loads(MANIFEST.read_text())), indent=2))
