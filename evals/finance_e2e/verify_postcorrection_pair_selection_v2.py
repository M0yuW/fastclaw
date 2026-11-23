#!/usr/bin/env python3
"""Verify the five provisional v2 exhibit pairs against archived filing indexes."""

from __future__ import annotations

import json
from datetime import date

from fetch_sources import ROOT, Source, validate_source, verify_local_lock


DISCOVERY = (ROOT / "results" /
             "2026-10-24-postcorrection-sec-source-discovery-v2" / "manifest.json")
MANIFEST = ROOT / "postcorrection_pair_sources_manifest_v2.json"
LOCK = ROOT / "postcorrection_pair_sources_lock_v2.json"


def verify(discovery: dict, manifest: dict) -> dict:
    sources = [Source(**item) for item in manifest["sources"]]
    for source in sources:
        validate_source(source)
    by_ticker = {issuer["ticker"]: issuer for issuer in discovery["issuers"]}
    if len(by_ticker) != 5 or len(sources) != 10:
        raise ValueError("v2 candidate inventory differs")
    decisions = []
    for ticker, issuer in by_ticker.items():
        candidates = issuer["candidate_filings"]
        chosen = [source for source in sources if source.symbol == ticker]
        if len(chosen) != 2:
            raise ValueError(f"v2 pair missing: {ticker}")
        chosen.sort(key=lambda source: source.filed_at)
        if ticker == "PNC":
            skipped = manifest["excluded_nonquarterly_candidate"]
            if (not candidates or skipped["ticker"] != ticker
                    or candidates[0]["accession"] != skipped["accession"]
                    or candidates[0]["ex99_1_urls"] != [skipped["url"]]
                    or "conference presentation" not in skipped["reason"]):
                raise ValueError("PNC nonquarterly skip is not documented")
            expected = candidates[1:3]
        else:
            expected = candidates[:2]
        if len(expected) != 2 or any(row["status"] != "ex99_1_found" for row in expected):
            raise ValueError(f"v2 pair lacks unique EX-99.1: {ticker}")
        expected.sort(key=lambda row: row["filing_date"])
        for source, row in zip(chosen, expected):
            if (source.accession != row["accession"]
                    or source.filed_at != row["filing_date"]
                    or source.url != row["ex99_1_urls"][0]):
                raise ValueError(f"v2 source selection differs from index: {ticker}")
        gap = (date.fromisoformat(chosen[1].filed_at)
               - date.fromisoformat(chosen[0].filed_at)).days
        if not 55 <= gap <= 130:
            raise ValueError(f"v2 filing gap outside shortlist rule: {ticker}")
        decisions.append({"ticker": ticker,
                          "baseline_accession": chosen[0].accession,
                          "event_accession": chosen[1].accession,
                          "filing_gap_days": gap,
                          "status": "provisional_pair_matches_archived_index"})
    return {"status": "v2_five_pair_shortlist_verified_period_and_basis_still_separate",
            "pairs": decisions}


if __name__ == "__main__":
    verify_local_lock(MANIFEST, LOCK)
    print(json.dumps(verify(json.loads(DISCOVERY.read_text()),
                            json.loads(MANIFEST.read_text())), indent=2))
