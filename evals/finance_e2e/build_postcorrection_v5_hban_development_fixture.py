#!/usr/bin/env python3
"""Free development-only correction for a v4 HBAN prompt omission.

HBAN was already observed in v4. This module must not be used to claim a
source-distinct confirmatory v5 answer-quality result.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal

import build_postcorrection_v4_event_preflight as v4


def corrected_hban_fixture(packet: dict | None = None) -> dict:
    prepared = v4.preflight()  # reruns the frozen source-row auditors
    fixture = copy.deepcopy(next(item for item in prepared["fixtures"]
                                 if item["runtime_symbol"] == "HBAN"))
    packet = packet if packet is not None else json.loads(
        v4.FIRST_PACKETS["HBAN"].read_text())
    notable = packet["event"]["notable_item"]
    gain = Decimal(notable["gaap_noninterest_income_gain_on_sale_usd_million"])
    adjusted = Decimal(notable["non_gaap_adjusted_noninterest_income_usd_million"])
    comparator = Decimal(notable[
        "non_gaap_adjusted_noninterest_income_prior_quarter_comparator_usd_million"])
    reported = Decimal(packet["event"]["facts"]["gaap_noninterest_income"])
    baseline = Decimal(packet["baseline"]["facts"]["gaap_noninterest_income"])
    if reported - gain != adjusted or comparator != baseline:
        raise ValueError("HBAN disclosed notable-item bridge does not reconcile")
    line = (
        "Q3 SEC-disclosed notable item: GAAP noninterest income "
        f"{reported} USD_million includes a {gain} USD_million gain on sale; "
        f"company-adjusted noninterest income excluding it is {adjusted} "
        f"USD_million [non_GAAP], versus the Q2 adjusted comparator {comparator} "
        f"USD_million [non_GAAP]. Reported sequential increase {reported-baseline}; "
        f"adjusted sequential increase {adjusted-comparator} USD_million. "
        "This is a disclosed arithmetic adjustment, not proof of why other fees changed."
    )
    fixture["numeric_context"] += "\n" + line
    fixture["event"]["summary"] += "; " + line
    fixture["event"]["observed_metrics"].update({
        "gaap_noninterest_income_gain_on_sale": {
            "value": str(gain), "unit": "USD_million",
            "fact_id": "V5-HBAN-Q3-GAIN-ON-SALE",
        },
        "non_gaap_adjusted_noninterest_income": {
            "value": str(adjusted), "unit": "USD_million",
            "fact_id": "V5-HBAN-Q3-ADJUSTED-NONINTEREST-INCOME",
        },
    })
    fixture["seed_thesis"]["required_event_metrics"].extend([
        "gaap_noninterest_income_gain_on_sale",
        "non_gaap_adjusted_noninterest_income",
    ])
    fixture["seed_thesis"]["required_event_metrics"].sort()
    fixture["status"] = "development_correction_seen_v4_case_not_confirmatory"
    return fixture


if __name__ == "__main__":
    fixture = corrected_hban_fixture()
    print(json.dumps({"case_id": fixture["case_id"],
                      "status": fixture["status"],
                      "required_metrics": len(fixture["seed_thesis"]["required_event_metrics"]),
                      "source_hash": fixture["event"]["sources"][0]["sha256"],
                      "new_context": fixture["numeric_context"].splitlines()[-1]},
                     indent=2))
