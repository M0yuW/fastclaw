#!/usr/bin/env python3
"""Check current-quarter labels near the start of each locked SEC exhibit."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from fetch_sources import ROOT, verify_local_lock
from sec_exhibit_text import extract_lines


MANIFEST = ROOT / "prospective_pair_sources_manifest_v1.json"
LOCK = ROOT / "prospective_pair_sources_lock_v1.json"
OUTPUT = ROOT / "prospective_period_headline_audit_v1.json"
PATTERNS = {
    "2025 Q2": re.compile(r"\b(?:second\s+quarter(?:\s+of)?\s+2025|2Q\s*25|Q2\s*2025|quarter\s+ended\s+June\s+30,?\s+2025)\b", re.I),
    "2025 Q3": re.compile(r"\b(?:third\s+quarter(?:\s+of)?\s+2025|3Q\s*25|Q3\s*2025|quarter\s+ended\s+September\s+30,?\s+2025)\b", re.I),
    "2024 Q4": re.compile(r"\b(?:fourth\s+quarter(?:\s+of)?\s+2024|4Q\s*24|Q4\s*2024)\b", re.I),
    "2025 Q1": re.compile(r"\b(?:first\s+quarter(?:\s+of)?\s+2025|1Q\s*25|Q1\s*2025)\b", re.I),
}


def anchor(lines: list[str], expected: str) -> dict:
    pattern = PATTERNS[expected]
    for index, line in enumerate(lines[:45]):
        combined = " ".join(lines[index:index + 2])
        match = pattern.search(combined)
        if match:
            return {"line": index + 1, "matched_text": match.group(0),
                    "context": re.sub(r"\s+", " ", combined)[:240]}
    raise ValueError(f"no near-headline period anchor for {expected}")


def audit(lock: dict) -> dict:
    entries = {entry["id"]: entry for entry in lock["entries"]}
    tickers = sorted({entry["symbol"] for entry in lock["entries"]})
    if len(tickers) != 20 or len(entries) != 40:
        raise ValueError("expected 20 issuer pairs")
    issuers = []
    for ticker in tickers:
        expected = (("2024 Q4", "2025 Q1") if ticker == "FOUR" else
                    ("2025 Q2", "2025 Q3"))
        periods = []
        for role, label in zip(("BASELINE", "EVENT"), expected):
            entry = entries[f"HOLDOUT-{ticker}-{role}-v1"]
            path = ROOT / entry["local_path"]
            hint = anchor(extract_lines(path), label)
            periods.append({"role": role.lower(), "expected_period": label,
                            "source_id": entry["id"], "source_sha256": entry["sha256"],
                            "headline_anchor": hint})
        issuers.append({"ticker": ticker, "periods": periods,
                        "status": "headline_period_anchor_match_not_full_basis_audit"})
    return {"version": 1, "status": "period_headline_anchors_match_no_model_observations",
            "lock_sha256": hashlib.sha256(LOCK.read_bytes()).hexdigest(),
            "issuers": issuers}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    result = audit(json.loads(LOCK.read_text(encoding="utf-8")))
    if OUTPUT.exists():
        raise SystemExit("period audit artifact exists; refusing to overwrite")
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"matched headline period anchors for {len(result['issuers'])} issuer pairs")
