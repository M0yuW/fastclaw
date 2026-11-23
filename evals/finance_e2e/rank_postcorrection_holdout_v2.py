#!/usr/bin/env python3
"""Verify the new, source-distinct post-correction candidate frame offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fetch_sources import ROOT
from rank_prospective_cross_workflow_v1 import SEED_SOURCE, rank


HERE = Path(__file__).resolve().parent
FRAME = HERE / "postcorrection_holdout_frame_v2.json"
RESULTS = HERE / "results" / "2026-10-23-prospective-event-batch1-flash-v1"
STRATA = ("banking_capital_markets", "payments_processing",
          "market_infrastructure_data", "credit_wealth")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def observed_v1_symbols() -> set[str]:
    frozen = {}
    for line in (RESULTS / "RESULT-SHA256.txt").read_text().splitlines():
        digest, relative = line.split(None, 1)
        frozen[relative.strip()] = digest
    paths = list(RESULTS.glob("*/result.json"))
    if {str(path.relative_to(RESULTS)) for path in paths} != set(frozen):
        raise ValueError("v1 raw result inventory differs from hash list")
    if any(sha256(path) != frozen[str(path.relative_to(RESULTS))] for path in paths):
        raise ValueError("v1 raw result hash differs")
    case_ids = {json.loads(path.read_text(encoding="utf-8"))["case_id"]
                for path in paths}
    if len(paths) != 25 or len(case_ids) != 5:
        raise ValueError("v1 observed case inventory differs")
    batch = json.loads((HERE / "prospective_event_batch1_v1.json").read_text())
    expected = {case["case_id"] for case in batch["cases"]}
    if case_ids != expected:
        raise ValueError("v1 observed cases differ from frozen first batch")
    return {json.loads((HERE / case["packet"]).read_text())["symbol"]
            for case in batch["cases"]}


def select(frame: dict, parent: dict, snapshot: dict, observed: set[str]) -> dict:
    if frame.get("version") != 2 or frame.get("paid_calls_authorized") is not False:
        raise ValueError("unexpected v2 frame or paid authorization flag")
    if observed != set(frame["excluded_v1_observed_issuers"]):
        raise ValueError("v2 exclusions differ from actual v1 observations")
    if snapshot.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError("SEC ticker snapshot schema differs")
    cik = {record[2]: str(record[0]).zfill(10) for record in snapshot["data"]}
    old = rank(parent, SEED_SOURCE.read_bytes())["strata"]
    selected = {}
    ranked_extensions = {}
    for stratum in STRATA:
        unobserved_primary = [ticker for ticker in old[stratum]["primary"]
                              if ticker not in observed]
        if unobserved_primary != frame["retained_unobserved_v1_primaries"][stratum]:
            raise ValueError(f"v2 retained primaries differ: {stratum}")
        reserve = old[stratum]["reserve"]
        if reserve != [frame["promoted_unobserved_v1_reserves"][stratum]]:
            raise ValueError(f"v2 reserve differs: {stratum}")
        pool = frame["extension_candidate_pools"][stratum]
        if len(pool) != len(set(pool)) or any(symbol not in cik for symbol in pool):
            raise ValueError(f"v2 extension pool invalid: {stratum}")
        if set(pool) & (set(parent["development_exclusions"]) |
                        set(parent["strata"][stratum]) | observed):
            raise ValueError(f"v2 extension pool overlaps excluded issuers: {stratum}")
        ranked_extensions[stratum] = sorted(
            pool, key=lambda symbol: hashlib.sha256(
                f"{frame['ranking_seed']}|{stratum}|{symbol}".encode()).hexdigest())
        chosen = unobserved_primary + reserve
        if stratum == "banking_capital_markets":
            if ranked_extensions[stratum][0] != frame["selected_extension_bank"]:
                raise ValueError("v2 new bank differs from predeclared hash rank")
            chosen.append(ranked_extensions[stratum][0])
        if len(chosen) != frame["target_issuers_per_stratum"]:
            raise ValueError(f"v2 selected stratum size differs: {stratum}")
        selected[stratum] = chosen
    all_symbols = [symbol for group in selected.values() for symbol in group]
    if len(all_symbols) != frame["target_independent_event_clusters"] or len(set(all_symbols)) != len(all_symbols):
        raise ValueError("v2 issuer count or source-distinctness differs")
    if set(all_symbols) & observed:
        raise ValueError("v2 selected an issuer with v1 model output")
    return {"status": "v2_candidate_frame_verified_no_model_observations",
            "selected_by_stratum": selected,
            "selected_cik": {symbol: cik[symbol] for symbol in all_symbols},
            "ranked_extensions": ranked_extensions,
            "selected_issuer_count": len(all_symbols), "planned_observations":
            len(all_symbols) * frame["repetitions_per_cluster"]}


def preflight() -> dict:
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    parent_path = HERE / frame["parent_v1_frame_path"]
    snapshot_path = ROOT / frame["issuer_identity_snapshot_path"]
    if sha256(parent_path) != frame["parent_v1_frame_sha256"]:
        raise ValueError("v1 parent frame hash differs")
    if sha256(snapshot_path) != frame["issuer_identity_snapshot_sha256"]:
        raise ValueError("SEC ticker snapshot hash differs")
    return select(frame, json.loads(parent_path.read_text()),
                  json.loads(snapshot_path.read_text()), observed_v1_symbols())


if __name__ == "__main__":
    print(json.dumps(preflight(), ensure_ascii=False, indent=2))
