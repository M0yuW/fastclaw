#!/usr/bin/env python3
"""Recheck archived SEC submission and filing-index discovery bytes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from discover_prospective_sec_exhibits_v1 import PARENT, exhibit_urls
from rank_prospective_cross_workflow_v1 import FRAME, ROOT, SEED_SOURCE, rank


EXHIBITS = ROOT / "results" / "2026-10-23-prospective-sec-exhibit-discovery-v1" / "manifest.json"


def checked_bytes(base: Path, relative: str, digest: str) -> bytes:
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():
        raise ValueError(f"missing or escaped discovery archive: {relative}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"discovery archive hash changed: {relative}")
    return raw


def verify(frame: dict, parent: dict, exhibits: dict) -> dict:
    ranked = rank(frame, SEED_SOURCE.read_bytes())
    primary = {ticker for groups in ranked["strata"].values() for ticker in groups["primary"]}
    if parent["frame_sha256"] != hashlib.sha256(FRAME.read_bytes()).hexdigest():
        raise ValueError("submission discovery frame hash mismatch")
    if exhibits["frame_sha256"] != parent["frame_sha256"]:
        raise ValueError("exhibit discovery frame hash mismatch")
    if exhibits["parent_manifest_sha256"] != hashlib.sha256(PARENT.read_bytes()).hexdigest():
        raise ValueError("parent submission manifest hash mismatch")
    if {item["ticker"] for item in parent["issuers"]} != primary:
        raise ValueError("submission discovery does not cover all primaries")
    parent_by_ticker = {item["ticker"]: item for item in parent["issuers"]}
    count = found = 0
    submission_dir = PARENT.parent
    exhibit_dir = EXHIBITS.parent
    for issuer in exhibits["issuers"]:
        ticker, cik = issuer["ticker"], issuer["cik"]
        prior = parent_by_ticker[ticker]
        if cik != prior["cik"] or cik != frame["cik_by_ticker"][ticker]:
            raise ValueError(f"CIK mismatch: {ticker}")
        for item in [prior["root_index"], *prior["shard_indexes"]]:
            checked_bytes(submission_dir, item["path"], item["sha256"])
        if len(issuer["candidates"]) != len(prior["earnings_8k_2_02_candidates"]):
            raise ValueError(f"candidate count changed: {ticker}")
        for candidate, filing in zip(issuer["candidates"], prior["earnings_8k_2_02_candidates"]):
            if candidate["accession"] != filing["accessionNumber"] or candidate["filing_date"] != filing["filingDate"]:
                raise ValueError(f"candidate identity changed: {ticker}")
            source = checked_bytes(exhibit_dir, candidate["index_path"], candidate["index_sha256"])
            urls = exhibit_urls(source.decode("utf-8", errors="replace"), candidate["accession"], cik)
            if urls != candidate["ex99_1_urls"]:
                raise ValueError(f"EX-99.1 discovery changed: {ticker} {candidate['accession']}")
            count += 1
            found += len(urls) == 1
    return {"status": "archived_discovery_hashes_and_exhibit_rows_match",
            "issuers": len(exhibits["issuers"]), "filing_candidates": count,
            "single_ex99_1_candidates": found, "model_observations": 0}


if __name__ == "__main__":
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    exhibits = json.loads(EXHIBITS.read_text(encoding="utf-8"))
    print(json.dumps(verify(frame, parent, exhibits), indent=2))
