#!/usr/bin/env python3
"""Verify a source-discovery roster excludes all observed v1/v2 issuers.

This is an offline selection check, not SEC-source eligibility or a model run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import verify_frozen_results
import rank_postcorrection_holdout_v2 as v2_rank


HERE = Path(__file__).parent
ROSTER = HERE / "postcorrection_unseen_source_candidates_v4.json"
V2_RESULTS = HERE / "results/2026-10-24-postcorrection-event-holdout-v2"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify() -> dict:
    roster = json.loads(ROSTER.read_text())
    if roster.get("version") != 4 or roster.get("paid_calls_authorized") is not False:
        raise ValueError("unexpected roster or authorization flag")
    if digest(v2_rank.FRAME) != roster["parent_v2_frame_sha256"]:
        raise ValueError("parent v2 frame hash changed")
    verify_frozen_results(V2_RESULTS)
    if digest(V2_RESULTS / "RESULT-SHA256.txt") != roster["stopped_v2_result_hash_list_sha256"]:
        raise ValueError("stopped v2 result hash list changed")
    selected = v2_rank.preflight()
    v2_symbols = set(selected["selected_cik"])
    observed_cases = {json.loads(path.read_text())["case_id"]
                      for path in V2_RESULTS.glob("*/result.json")}
    import build_postcorrection_event_preflight_v2 as source_batch
    selected_cases = {json.loads(path.read_text())["case_id"]
                      for symbol, (_, path) in source_batch.READY.items()
                      if symbol in v2_symbols}
    if observed_cases != selected_cases:
        raise ValueError("v2 observed case coverage differs from all 20 selected cases")
    seed = hashlib.sha256(v2_rank.FRAME.read_bytes()
                          + b"|v4-unused-source-discovery").hexdigest()
    if seed != roster["ranking_seed"]:
        raise ValueError("candidate ranking seed changed")
    parent = json.loads(v2_rank.FRAME.read_text())
    ranked = {}
    for stratum, pool in parent["extension_candidate_pools"].items():
        unused = [symbol for symbol in pool if symbol not in v2_symbols]
        ranked[stratum] = sorted(unused, key=lambda symbol: hashlib.sha256(
            f"{seed}|{stratum}|{symbol}".encode()).hexdigest())
    if ranked != roster["ranked_unseen_candidates"]:
        raise ValueError("ranked unused candidate pool changed")
    initial = {name: symbols[:5] for name, symbols in ranked.items()}
    if initial != roster["initial_five_per_stratum"]:
        raise ValueError("initial candidates differ from ranking")
    all_symbols = [symbol for group in initial.values() for symbol in group]
    if (len(all_symbols) != roster["initial_candidate_count"]
            or len(set(all_symbols)) != len(all_symbols)
            or set(all_symbols) & (v2_symbols | v2_rank.observed_v1_symbols())):
        raise ValueError("candidate count, uniqueness or source distinction failed")
    if sum(map(len, ranked.values())) != roster["available_ranked_candidate_count"]:
        raise ValueError("available candidate count changed")
    if ranked["banking_capital_markets"][5:] != roster["banking_source_ineligibility_reserves"]:
        raise ValueError("banking replacement order changed")
    return {"status": "unseen_source_discovery_roster_verified_not_final_panel",
            "initial_candidates": len(all_symbols),
            "ranked_candidates": sum(map(len, ranked.values())),
            "v2_observed_issuers_excluded": len(v2_symbols),
            "model_observations": 0,
            "selected_by_stratum": initial}


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
