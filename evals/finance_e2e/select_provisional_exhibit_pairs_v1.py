#!/usr/bin/env python3
"""Shortlist paired SEC exhibits by filing dates; fiscal adjacency remains unverified."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from verify_prospective_sec_discovery_v1 import EXHIBITS, ROOT


OUTPUT = ROOT / "prospective_provisional_exhibit_pairs_v1.json"


def choose_pair(candidates: list[dict]) -> tuple[dict, dict]:
    usable = [item for item in candidates if len(item["ex99_1_urls"]) == 1]
    usable.sort(key=lambda item: (item["filing_date"], item["accession"]), reverse=True)
    for newer in usable:
        for older in usable:
            gap = (date.fromisoformat(newer["filing_date"])
                   - date.fromisoformat(older["filing_date"])).days
            if 55 <= gap <= 130:
                return older, newer
    raise ValueError("no EX-99.1 filing pair with a plausible quarterly date gap")


def select(exhibits: dict) -> dict:
    issuers = []
    for issuer in exhibits["issuers"]:
        older, newer = choose_pair(issuer["candidates"])
        issuers.append({"ticker": issuer["ticker"], "cik": issuer["cik"],
                        "status": "provisional_filing_gap_only_fiscal_period_unverified",
                        "baseline": {"filed_at": older["filing_date"],
                                     "accession": older["accession"],
                                     "source_url": older["ex99_1_urls"][0]},
                        "event": {"filed_at": newer["filing_date"],
                                  "accession": newer["accession"],
                                  "source_url": newer["ex99_1_urls"][0]}})
    return {"version": 1, "status": "provisional_pairs_no_model_observations",
            "exhibit_manifest_sha256": hashlib.sha256(EXHIBITS.read_bytes()).hexdigest(),
            "filing_gap_days_inclusive": [55, 130], "issuers": issuers}


if __name__ == "__main__":
    exhibits = json.loads(EXHIBITS.read_text(encoding="utf-8"))
    result = select(exhibits)
    if OUTPUT.exists():
        raise SystemExit("provisional pair manifest already exists; refusing to overwrite")
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    for issuer in result["issuers"]:
        print(f"{issuer['ticker']}: {issuer['baseline']['filed_at']} -> {issuer['event']['filed_at']}")
