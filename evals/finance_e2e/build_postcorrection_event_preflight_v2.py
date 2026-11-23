#!/usr/bin/env python3
"""Source-audited, model-free v2 event fixtures for the frozen issuer frame.

This is a source/numeric preflight, not a 100-observation run or paid authorization.
The generated prompt contains only audited facts, host arithmetic, and workflow
instructions; it never includes private interpretation checks or old answers.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import audit_axp_holdout_facts_v2 as axp
import audit_ally_holdout_facts_v2 as ally
import audit_bac_holdout_facts_v1 as bac
import audit_cme_holdout_facts_v1 as cme
import audit_cboe_holdout_facts_v2 as cboe
import audit_cof_holdout_facts_v2 as cof
import audit_fis_holdout_facts_v2 as fis
import audit_four_holdout_facts_v2 as four
import audit_gpn_holdout_facts_v2 as gpn
import audit_ibkr_holdout_facts_v2 as ibkr
import audit_ice_holdout_facts_v2 as ice
import audit_msci_holdout_facts_v2 as msci
import audit_ndaq_holdout_facts_v2 as ndaq
import audit_jpm_holdout_facts_v2 as jpm
import audit_pnc_holdout_facts_v2 as pnc
import audit_schw_holdout_facts_v2 as schw
import audit_stt_holdout_facts_v2 as stt
import audit_syf_holdout_facts_v2 as syf
import audit_wfc_holdout_facts_v2 as wfc
import audit_wu_holdout_facts_v2 as wu
from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import check_adjacent_quarters
from rank_postcorrection_holdout_v2 import preflight as verify_frame
from selected_fact_delta_guard_v1 import decompose_change, derive, render_trusted_numeric_context


HERE = Path(__file__).resolve().parent
READY = {
    "BAC": (bac, HERE / "bac_holdout_fact_packet_v1.json"),
    "CME": (cme, HERE / "cme_holdout_fact_packet_v1.json"),
    "WFC": (wfc, HERE / "wfc_holdout_fact_packet_v2.json"),
    "AXP": (axp, HERE / "axp_holdout_fact_packet_v2.json"),
    "PNC": (pnc, HERE / "pnc_holdout_fact_packet_v2.json"),
    "CBOE": (cboe, HERE / "cboe_holdout_fact_packet_v2.json"),
    "ALLY": (ally, HERE / "ally_holdout_fact_packet_v2.json"),
    "STT": (stt, HERE / "stt_holdout_fact_packet_v2.json"),
    "ICE": (ice, HERE / "ice_holdout_fact_packet_v2.json"),
    "MSCI": (msci, HERE / "msci_holdout_fact_packet_v2.json"),
    "NDAQ": (ndaq, HERE / "ndaq_holdout_fact_packet_v2.json"),
    "JPM": (jpm, HERE / "jpm_holdout_fact_packet_v2.json"),
    "FIS": (fis, HERE / "fis_holdout_fact_packet_v2.json"),
    "GPN": (gpn, HERE / "gpn_holdout_fact_packet_v2.json"),
    "SYF": (syf, HERE / "syf_holdout_fact_packet_v2.json"),
    "WU": (wu, HERE / "wu_holdout_fact_packet_v2.json"),
    "SCHW": (schw, HERE / "schw_holdout_fact_packet_v2.json"),
    "IBKR": (ibkr, HERE / "ibkr_holdout_fact_packet_v2.json"),
    "COF": (cof, HERE / "cof_holdout_fact_packet_v2.json"),
    "FOUR": (four, HERE / "four_holdout_fact_packet_v2.json"),
}
MODEL_UNIT = {
    "USD_million_rounded": "USD_million",
    "USD_thousand_reported": "USD_thousand",
    "USD_billion_reported": "USD_billion",
    "USD_per_share_reported": "USD_per_share",
    "million_shares_reported": "million_shares",
    "million_accounts_reported": "million_accounts",
    "thousand_shares_reported": "thousand_shares",
    "percent": "percent",
}
REVENUE_MIX = {
    "BAC": ("gaap_total_revenue_net_of_interest_expense",
            ["gaap_net_interest_income", "gaap_noninterest_income"]),
    "WFC": ("gaap_total_revenue",
            ["gaap_net_interest_income", "gaap_noninterest_income"]),
    "PNC": ("gaap_revenue",
            ["gaap_net_interest_income", "gaap_noninterest_income"]),
    "CBOE": ("gaap_net_revenue", cboe.SEGMENTS),
    "ALLY": ("gaap_total_net_revenue",
             ["gaap_net_financing_revenue", "gaap_other_revenue"]),
    "STT": ("gaap_total_revenue",
            ["gaap_total_fee_revenue", "gaap_net_interest_income"]),
    "ICE": ("gaap_total_gross_revenue",
            ["gaap_exchanges_gross_revenue", "gaap_fixed_income_data_gross_revenue",
             "gaap_mortgage_technology_gross_revenue"]),
    "NDAQ": ("gaap_total_gross_revenue", ndaq.SEGMENTS),
    "FIS": ("gaap_consolidated_revenue", list(fis.REVENUE_COMPONENTS)),
    "SCHW": ("gaap_total_net_revenues", list(schw.REVENUE_COMPONENTS)),
    "IBKR": ("gaap_total_net_revenues", list(ibkr.REVENUE_COMPONENTS)),
    "FOUR": ("gaap_gross_revenue", list(four.REVENUE_COMPONENTS)),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_ref(packet: dict, role: str, lock: dict) -> dict:
    section = packet[role]
    candidates = [entry for entry in lock["entries"]
                  if entry["url"] == section["source_url"]
                  and entry["sha256"] == section["source_sha256"]]
    if len(candidates) != 1:
        raise ValueError(f"source lock reference is not unique: {packet['symbol']} {role}")
    return {"id": candidates[0]["id"], "url": section["source_url"],
            "sha256": section["source_sha256"]}


def _fact_text(section: dict) -> str:
    return "; ".join(f"{fact['id']}={fact['value']} {MODEL_UNIT[fact['unit']]}"
                     for fact in section["facts"])


def review_prompt(fixture: dict, thesis_id: str, alert_id: str) -> str:
    return (
        "Historical source-bounded SEC research-state replay, not a trade request. "
        "Read the stored thesis and earnings alert using finance tools. The host-checked "
        "numeric context below is arithmetic on selected source rows, not a causal "
        "explanation or complete filing. Distinguish sequential from year-over-year "
        "figures, reported from adjusted measures, and percentage points from relative "
        "percent. Independently explain a supported implication, a material counterpoint, "
        "missing evidence, and your own research-state decision. Do not infer absolute "
        "loss dollars from a rate or attribute a total to listed components when a "
        "residual remains. Persist one source-linked version-protected review, acknowledge "
        "the alert, and verify that any needs_review decision leaves the thesis blocked. "
        "Do not trade.\n\n"
        + fixture["numeric_context"] + "\n\n"
        + f"Case {fixture['case_id']}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


def fixture(packet: dict, lock: dict) -> dict:
    check_adjacent_quarters(packet["baseline"]["period"], packet["event"]["period"])
    if "sec_event_to_thesis_review" not in packet["workflow_eligibility"]:
        raise ValueError("packet not eligible for SEC event workflow")
    symbol = packet["symbol"]
    before, after = packet["baseline"], packet["event"]
    before_metrics = {fact["metric"]: fact["unit"] for fact in before["facts"]}
    after_metrics = {fact["metric"]: fact["unit"] for fact in after["facts"]}
    if before_metrics != after_metrics or len(before_metrics) != len(before["facts"]):
        raise ValueError("metric/unit set differs between adjacent quarters")
    delta = derive(packet)
    mixes = ([decompose_change(delta, *REVENUE_MIX[symbol])]
             if symbol in REVENUE_MIX else [])
    numeric_context = render_trusted_numeric_context(delta, mixes)
    observed = {fact["metric"]: {
        "value": str(fact["value"]), "unit": MODEL_UNIT[fact["unit"]],
        "fact_id": fact["id"],
    } for fact in after["facts"]}
    seed = {
        "market": "US", "symbol": symbol,
        "title": f"{symbol} source-bounded earnings thesis",
        "thesis": (f"Baseline {before['period']}: {_fact_text(before)}. Review the next "
                   "filing for changes, contrary evidence and missing context. "
                   "No valuation or trading conclusion has been established."),
        "status": "active", "conviction": 3,
        "required_event_metrics": sorted(observed),
        "evidence": [_source_ref(packet, "baseline", lock)],
    }
    event = {
        "external_id": f"HOLDOUT-V2-{symbol}-EVENT",
        "type": "earnings", "as_of": after["as_of"],
        "summary": (f"{symbol} {after['period']} SEC selected-fact packet: "
                    f"{_fact_text(after)}."),
        "sources": [_source_ref(packet, "event", lock)],
        "observed_metrics": observed,
    }
    return {"case_id": packet["case_id"], "runtime_symbol": symbol,
            "seed_thesis": seed, "event": event,
            "numeric_context": numeric_context,
            "packet_sha256": _sha256(READY[symbol][1])}


def preflight() -> dict:
    selected = verify_frame()["selected_cik"]
    for manifest, lock in ((bac.MANIFEST, bac.LOCK), (wfc.MANIFEST, wfc.LOCK)):
        verify_local_lock(manifest, lock)
    old_lock = json.loads(bac.LOCK.read_text())
    new_lock = json.loads(wfc.LOCK.read_text())
    fixtures = []
    for symbol, (auditor, path) in READY.items():
        packet = json.loads(path.read_text())
        if packet["symbol"] != symbol or packet["cik"] != selected[symbol]:
            raise ValueError(f"audited packet differs from v2 selected issuer: {symbol}")
        lock = old_lock if symbol in ("BAC", "CME", "STT", "ICE", "MSCI", "NDAQ", "JPM", "FIS", "GPN", "SYF", "WU", "SCHW", "IBKR", "COF", "FOUR") else new_lock
        auditor.audit(packet, lock)
        model_input = fixture(packet, lock)
        serialized = json.dumps(model_input, ensure_ascii=False)
        if "precommitted_interpretation_checks" in serialized:
            raise ValueError("private oracle leaked into model input")
        if any(check in serialized for check in packet["precommitted_interpretation_checks"]):
            raise ValueError("private interpretation check leaked")
        fixtures.append(model_input)
    return {"status": "v2_source_and_numeric_preflight_complete_no_model_observations",
            "ready_cases": len(fixtures), "target_cases": len(selected),
            "model_observations": 0, "paid_calls_authorized": False,
            "fixtures": fixtures}


if __name__ == "__main__":
    result = preflight()
    print(json.dumps({key: value for key, value in result.items() if key != "fixtures"},
                     ensure_ascii=False, indent=2))
