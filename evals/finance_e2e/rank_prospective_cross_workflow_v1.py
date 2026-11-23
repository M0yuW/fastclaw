#!/usr/bin/env python3
"""Validate and rank the frozen candidate frame; never select by model outcome."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRAME = ROOT / "prospective_cross_workflow_frame_v1.json"
SEED_SOURCE = ROOT / "INSIGHT-STABILITY-EVIDENCE-PLAN-2026-10-23.md"


def verify_identity_snapshot(frame: dict, raw_snapshot: bytes) -> None:
    if hashlib.sha256(raw_snapshot).hexdigest() != frame["issuer_identity_snapshot_sha256"]:
        raise ValueError("SEC ticker snapshot hash changed")
    snapshot = json.loads(raw_snapshot)
    if snapshot.get("fields") != ["cik", "name", "ticker", "exchange"]:
        raise ValueError("unexpected SEC ticker snapshot schema")
    listed = {record[2]: record[0] for record in snapshot["data"]}
    for ticker, cik in frame["cik_by_ticker"].items():
        if listed.get(ticker) != int(cik):
            raise ValueError(f"SEC ticker/CIK mismatch: {ticker}")


def rank(frame: dict, seed_source: bytes) -> dict:
    if frame.get("version") != 1:
        raise ValueError("unsupported frame version")
    seed = hashlib.sha256(seed_source).hexdigest()
    if frame["selection_seed"] != seed:
        raise ValueError("selection seed source changed")
    selected_count = frame["selected_per_stratum"]
    excluded = set(frame["development_exclusions"])
    candidates = [symbol for group in frame["strata"].values() for symbol in group]
    if len(candidates) != len(set(candidates)):
        raise ValueError("duplicate candidate ticker")
    if set(candidates) & excluded:
        raise ValueError("development ticker entered prospective frame")
    ciks = frame["cik_by_ticker"]
    if (set(ciks) != set(candidates) or len(set(ciks.values())) != len(ciks)
            or any(len(value) != 10 or not value.isdecimal() for value in ciks.values())):
        raise ValueError("candidate CIK identities are missing, duplicated, or malformed")
    if len(frame["planned_workflows"]) != 3 or len(set(frame["planned_workflows"])) != 3:
        raise ValueError("expected three distinct workflows")
    strata = {}
    for name, group in sorted(frame["strata"].items()):
        if len(group) <= selected_count or any(not ticker.isupper() for ticker in group):
            raise ValueError(f"invalid stratum {name}")
        order = sorted(group, key=lambda ticker: hashlib.sha256(
            f"{seed}:{name}:{ticker}".encode("ascii")).hexdigest())
        strata[name] = {"primary": order[:selected_count], "reserve": order[selected_count:]}
    return {"selection_seed": seed, "strata": strata,
            "primary_count": sum(len(v["primary"]) for v in strata.values()),
            "reserve_count": sum(len(v["reserve"]) for v in strata.values())}


if __name__ == "__main__":
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    verify_identity_snapshot(frame, (ROOT / frame["issuer_identity_snapshot_path"]).read_bytes())
    print(json.dumps(rank(frame, SEED_SOURCE.read_bytes()), indent=2))
