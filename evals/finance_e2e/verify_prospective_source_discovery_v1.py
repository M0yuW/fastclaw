#!/usr/bin/env python3
"""Verify frozen SEC bytes and filing-index exhibit identity, not fact semantics."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from rank_prospective_cross_workflow_v1 import FRAME, ROOT, SEED_SOURCE, rank, verify_identity_snapshot


DISCOVERY = ROOT / "prospective_holdout_source_discovery_v1.json"


def verify(frame: dict, discovery: dict) -> dict:
    order = rank(frame, SEED_SOURCE.read_bytes())
    primaries = {ticker: stratum for stratum, groups in order["strata"].items()
                 for ticker in groups["primary"]}
    if discovery.get("version") != 1 or discovery.get("frame") != FRAME.name:
        raise ValueError("discovery manifest version/frame mismatch")
    seen = set()
    for issuer in discovery["issuers"]:
        ticker = issuer["ticker"]
        if ticker in seen or primaries.get(ticker) != issuer["stratum"]:
            raise ValueError(f"duplicate or non-primary issuer: {ticker}")
        seen.add(ticker)
        if issuer["cik"] != frame["cik_by_ticker"][ticker]:
            raise ValueError(f"CIK mismatch: {ticker}")
        sources = issuer["sources"]
        if len(sources) != 2:
            raise ValueError(f"expected a pair of sources: {ticker}")
        parsed_periods = []
        for source in sources:
            match = re.fullmatch(r"(\d{4}) Q([1-4])", source["fiscal_period"])
            if not match:
                raise ValueError(f"unparseable fiscal period: {ticker}")
            parsed_periods.append(int(match.group(1)) * 4 + int(match.group(2)))
        if parsed_periods[1] != parsed_periods[0] + 1:
            raise ValueError(f"nonadjacent fiscal pair: {ticker}")
        if not 75 <= (date.fromisoformat(sources[1]["period_end"])
                      - date.fromisoformat(sources[0]["period_end"])).days <= 110:
            raise ValueError(f"unexpected quarter-end spacing: {ticker}")
        for source in sources:
            for field, hash_field in (("local_path", "sha256"),
                                      ("filing_index_path", "filing_index_sha256")):
                path = (ROOT / source[field]).resolve()
                if not path.is_relative_to(ROOT) or not path.is_file():
                    raise ValueError(f"missing or escaped source path: {path}")
                if hashlib.sha256(path.read_bytes()).hexdigest() != source[hash_field]:
                    raise ValueError(f"source hash changed: {path}")
            url = urlparse(source["url"])
            accession_compact = source["accession"].replace("-", "")
            expected_prefix = f"/Archives/edgar/data/{int(issuer['cik'])}/{accession_compact}/"
            if url.scheme != "https" or url.hostname != "www.sec.gov" or not url.path.startswith(expected_prefix):
                raise ValueError(f"SEC URL identity mismatch: {ticker}")
            if source["form"] != "8-K" or source["document_type"] != "EX-99.1":
                raise ValueError(f"wrong filing type: {ticker}")
            index_html = (ROOT / source["filing_index_path"]).read_text(encoding="utf-8")
            filename = url.path.rsplit("/", 1)[-1]
            matching_rows = [row for row in re.findall(r"<tr\b[^>]*>.*?</tr>", index_html,
                                                           flags=re.IGNORECASE | re.DOTALL)
                             if filename in row]
            if len(matching_rows) != 1 or len(re.findall(r">EX-99\.1<", matching_rows[0])) < 2:
                raise ValueError(f"filing index does not identify EX-99.1: {ticker}")
            if source["filed_at"] > frame["filing_cutoff"]:
                raise ValueError(f"source filed after cutoff: {ticker}")
    return {"status": "source_hashes_and_exhibit_identity_match",
            "issuer_pairs": len(seen), "source_files": 2 * len(seen),
            "fact_semantics_audited": False, "model_observations": 0}


if __name__ == "__main__":
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    verify_identity_snapshot(frame, (ROOT / frame["issuer_identity_snapshot_path"]).read_bytes())
    discovery = json.loads(DISCOVERY.read_text(encoding="utf-8"))
    print(json.dumps(verify(frame, discovery), indent=2))
