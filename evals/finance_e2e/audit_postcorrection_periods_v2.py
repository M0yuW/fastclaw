#!/usr/bin/env python3
"""Check quarter labels near the start of five locked v2 SEC exhibits."""

from __future__ import annotations

import hashlib
import json

from audit_prospective_period_headlines_v1 import anchor
from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines


MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"
OUTPUT = ROOT / "postcorrection_period_headline_audit_v2.json"
TICKERS = ("PNC", "AXP", "CBOE", "ALLY", "WFC")


def audit(lock: dict) -> dict:
    entries = {entry["id"]: entry for entry in lock["entries"]}
    if len(entries) != 10 or {entry["symbol"] for entry in entries.values()} != set(TICKERS):
        raise ValueError("v2 new-source pair inventory differs")
    issuers = []
    for ticker in TICKERS:
        periods = []
        for role, expected in (("BASELINE", "2025 Q2"), ("EVENT", "2025 Q3")):
            entry = entries[f"HOLDOUT-V2-{ticker}-{role}"]
            hint = anchor(extract_lines(ROOT / entry["local_path"]), expected)
            periods.append({"role": role.lower(), "expected_period": expected,
                            "source_id": entry["id"], "source_sha256": entry["sha256"],
                            "headline_anchor": hint})
        issuers.append({"ticker": ticker, "periods": periods,
                        "status": "headline_period_anchor_match_not_full_basis_audit"})
    return {"version": 2,
            "status": "new_v2_period_headline_anchors_match_no_model_observations",
            "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            "issuers": issuers}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    result = audit(json.loads(LOCK.read_text(encoding="utf-8")))
    if OUTPUT.exists():
        raise SystemExit("v2 period audit artifact exists; refusing overwrite")
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"matched near-headline quarter labels for {len(result['issuers'])} issuer pairs")
