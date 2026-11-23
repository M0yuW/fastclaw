#!/usr/bin/env python3
"""Convert frozen provisional pairs to a SEC-only fetch manifest.

This does not certify fiscal adjacency, comparable measures or insight quality.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from rank_prospective_cross_workflow_v1 import FRAME, ROOT
from select_provisional_exhibit_pairs_v1 import OUTPUT as PAIRS


OUTPUT = ROOT / "prospective_pair_sources_manifest_v1.json"


def build(frame: dict, pairs: dict, identity_snapshot: dict) -> dict:
    if pairs["exhibit_manifest_sha256"] != hashlib.sha256(
            (ROOT / "results/2026-10-23-prospective-sec-exhibit-discovery-v1/manifest.json").read_bytes()).hexdigest():
        raise ValueError("provisional pairs do not match frozen exhibit discovery")
    names = {str(row[0]).zfill(10): row[1] for row in identity_snapshot["data"]}
    sources = []
    seen = set()
    for case_no, issuer in enumerate(pairs["issuers"], 1):
        ticker, cik = issuer["ticker"], issuer["cik"]
        if cik != frame["cik_by_ticker"][ticker] or cik not in names:
            raise ValueError(f"issuer identity not in frozen SEC snapshot: {ticker}")
        for episode, period in enumerate(("baseline", "event"), 1):
            entry = issuer[period]
            parsed = urlparse(entry["source_url"])
            expected = f"/Archives/edgar/data/{int(cik)}/{entry['accession'].replace('-', '')}/"
            if parsed.scheme != "https" or parsed.hostname != "www.sec.gov" or not parsed.path.startswith(expected):
                raise ValueError(f"source URL does not match CIK/accession: {ticker}")
            artifact = parsed.path.rsplit("/", 1)[-1]
            source_id = f"HOLDOUT-{ticker}-{period.upper()}-v1"
            if source_id in seen:
                raise ValueError(f"duplicate source ID: {source_id}")
            seen.add(source_id)
            sources.append({"id": source_id, "company": names[cik], "symbol": ticker,
                            "cik": cik, "url": entry["source_url"],
                            "filed_at": entry["filed_at"],
                            "accession": entry["accession"], "artifact": artifact,
                            "form": "8-K", "document_type": "EX-99.1",
                            "episode": case_no * 2 - (1 if episode == 1 else 0)})
    return {"version": 1, "dataset": "prospective-cross-workflow-holdout-v1-provisional",
            "status": "source_artifact_download_manifest_period_unverified",
            "provisional_pairs_sha256": hashlib.sha256(PAIRS.read_bytes()).hexdigest(),
            "sources": sources}


if __name__ == "__main__":
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    snapshot = json.loads((ROOT / frame["issuer_identity_snapshot_path"]).read_text(encoding="utf-8"))
    result = build(frame, pairs, snapshot)
    if OUTPUT.exists():
        raise SystemExit("source download manifest already exists; refusing to overwrite")
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {len(result['sources'])} source artifact URLs")
