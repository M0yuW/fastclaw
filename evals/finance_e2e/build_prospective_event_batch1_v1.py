#!/usr/bin/env python3
"""Preflight source-audited, inference-neutral event/ledger inputs for batch 1.

This module does not contact a model or write a ledger. The expectation text in
the source packets is deliberately excluded from every returned model input.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import audit_bny_holdout_facts_v1 as bny
import audit_fisv_holdout_facts_v1 as fisv
import audit_gs_holdout_facts_v1 as gs
import audit_mco_holdout_facts_v1 as mco
import audit_omf_holdout_facts_v1 as omf
from fetch_sources import ROOT, verify_local_lock
from financial_evidence_bundle_v1 import check_adjacent_quarters
from rank_prospective_cross_workflow_v1 import (
    FRAME, SEED_SOURCE, rank, verify_identity_snapshot,
)
from verify_prospective_source_discovery_v1 import DISCOVERY


HERE = Path(__file__).resolve().parent
FRAME_PATH = HERE / "prospective_event_batch1_v1.json"
LOCK_PATH = HERE / "prospective_pair_sources_lock_v1.json"
MANIFEST_PATH = HERE / "prospective_pair_sources_manifest_v1.json"
AUDITORS = {"GS": gs, "BNY": bny, "FISV": fisv, "MCO": mco, "OMF": omf}
UNIT = {"USD_million_rounded": "USD_million", "percent": "percent"}
SOURCE_SIGNALS = {
    "FISV": ("Issuer Q3 release says 'guidance reset' and 'current performance is not "
             "where we want it'; these are management statements."),
    "MCO": ("Issuer Q3 release says Moody's Analytics transaction revenue declined "
            "19% versus the prior-year period; this is a segment disclosure."),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_ref(packet: dict, period: str) -> dict:
    source = packet[period]
    return {"id": f"HOLDOUT-{packet['symbol']}-{period.upper()}-v1",
            "url": source["source_url"], "sha256": source["source_sha256"]}


def fact_text(facts: list[dict]) -> str:
    return "; ".join(f"{fact['id']}={fact['value']} {UNIT[fact['unit']]}"
                     for fact in facts)


def validate_case(packet: dict, case: dict) -> None:
    if packet["case_id"] != case["case_id"]:
        raise ValueError("batch case ID differs from source packet")
    if "sec_event_to_thesis_review" not in packet["workflow_eligibility"]:
        raise ValueError("packet is not eligible for event workflow")
    if not case["runtime_symbol"] or not case["runtime_symbol"].isupper():
        raise ValueError("invalid historical runtime symbol")
    check_adjacent_quarters(packet["baseline"]["period"], packet["event"]["period"])
    for period in ("baseline", "event"):
        facts = packet[period]["facts"]
        if not facts or len({f["id"] for f in facts}) != len(facts):
            raise ValueError(f"missing or duplicate fact IDs: {period}")
        if len({f["metric"] for f in facts}) != len(facts):
            raise ValueError(f"duplicate metric names: {period}")
        if any(f["unit"] not in UNIT for f in facts):
            raise ValueError(f"unsupported source fact unit: {period}")
    before = {f["metric"]: f["unit"] for f in packet["baseline"]["facts"]}
    after = {f["metric"]: f["unit"] for f in packet["event"]["facts"]}
    if before != after:
        raise ValueError("event and baseline metric/unit sets differ")


def fixture(packet: dict, runtime_symbol: str) -> dict:
    """Return only information permissible in a fresh model/ledger session."""
    baseline = packet["baseline"]
    event = packet["event"]
    metrics = {fact["metric"]: {"value": str(fact["value"]),
                                "unit": UNIT[fact["unit"]], "fact_id": fact["id"]}
               for fact in event["facts"]}
    seed = {
        "market": "US", "symbol": runtime_symbol,
        "title": f"{runtime_symbol} source-bounded earnings thesis",
        "thesis": (f"Baseline {baseline['period']}: {fact_text(baseline['facts'])}. "
                   "Review the next filing for changes, contrary evidence, and missing context. "
                   "No valuation or trading conclusion has been established."),
        "status": "active", "conviction": 3,
        "required_event_metrics": sorted(metrics),
        "evidence": [source_ref(packet, "baseline")],
    }
    source_signal = SOURCE_SIGNALS.get(packet["symbol"])
    if source_signal and "qualitative_source_signal" not in packet:
        raise ValueError("source signal missing from frozen packet")
    incoming = {
        "external_id": f"HOLDOUT-{packet['symbol']}-EVENT-v1",
        "type": "earnings", "as_of": event["as_of"],
        "summary": (f"{runtime_symbol} {event['period']} SEC selected-fact packet: "
                    + fact_text(event["facts"]) + "."
                    + (" " + source_signal if source_signal else "")),
        "sources": [source_ref(packet, "event")],
        "observed_metrics": metrics,
    }
    return {"case_id": packet["case_id"], "runtime_symbol": runtime_symbol,
            "seed_thesis": seed, "event": incoming}


def preflight() -> dict:
    frame = json.loads(FRAME_PATH.read_text(encoding="utf-8"))
    if (frame["version"] != 1 or frame["workflow"] != "sec_event_to_thesis_review" or
            frame["repetitions_per_case"] != 5 or not frame["fresh_session_and_ledger_per_observation"] or
            not frame["no_outcome_based_retries"]):
        raise ValueError("batch design differs from frozen protocol")
    if len(frame["cases"]) != 5 or len({c["case_id"] for c in frame["cases"]}) != 5:
        raise ValueError("batch must contain five distinct cases")
    verify_local_lock(MANIFEST_PATH, LOCK_PATH)
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    prospective_frame = json.loads(FRAME.read_text(encoding="utf-8"))
    verify_identity_snapshot(
        prospective_frame,
        (HERE / prospective_frame["issuer_identity_snapshot_path"]).read_bytes())
    selected = rank(prospective_frame, SEED_SOURCE.read_bytes())
    primaries = {symbol for group in selected["strata"].values()
                 for symbol in group["primary"]}
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    fixtures = []
    source_hashes = {}
    for case in frame["cases"]:
        path = HERE / case["packet"]
        packet = json.loads(path.read_text(encoding="utf-8"))
        validate_case(packet, case)
        if packet["symbol"] not in primaries:
            raise ValueError("batch contains a non-primary prospective issuer")
        if packet.get("cik") != prospective_frame["cik_by_ticker"][packet["symbol"]]:
            raise ValueError("packet CIK differs from frozen issuer frame")
        auditor = AUDITORS[packet["symbol"]]
        if packet["symbol"] == "GS":
            auditor.audit(packet, prospective_frame, discovery)
        else:
            auditor.audit(packet, lock)
        source_hashes[packet["case_id"]] = sha256(path)
        fixtures.append(fixture(packet, case["runtime_symbol"]))
    return {"status": "source_audited_fixture_preflight_only",
            "cases": len(fixtures), "planned_observations": len(fixtures) * 5,
            "source_packet_sha256": source_hashes, "fixtures": fixtures,
            "model_observations": 0}


if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2, ensure_ascii=False))
