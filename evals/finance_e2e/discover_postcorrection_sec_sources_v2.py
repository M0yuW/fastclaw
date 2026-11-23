#!/usr/bin/env python3
"""Archive SEC candidate indexes for five as-yet-unseen v2 issuers.

Discovery is not a period/basis audit or an eligibility determination. No
model service is contacted. Public source bytes and hashes are retained.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from discover_prospective_sec_exhibits_v1 import exhibit_urls, fetch_index
from discover_prospective_sec_submissions_v1 import (
    earnings_candidates, fetch_json, matching_shards, records_from_arrays,
)
from rank_postcorrection_holdout_v2 import preflight


HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = (HERE / "results" /
                  "2026-10-24-postcorrection-sec-source-discovery-v2")
TARGETS = ("PNC", "AXP", "CBOE", "ALLY", "WFC")
START = "2025-01-01"
CUTOFF = "2025-12-31"


def selected_targets() -> dict[str, str]:
    ranked = preflight()
    selected = ranked["selected_cik"]
    old_lock = json.loads((HERE / "prospective_pair_sources_lock_v1.json").read_text())
    downloaded = {entry["symbol"] for entry in old_lock["entries"]}
    if set(TARGETS) != set(selected) - downloaded:
        raise ValueError("v2 missing-source targets differ from frozen selection")
    return {ticker: selected[ticker] for ticker in TARGETS}


def discover(output: Path, user_agent: str, delay: float = 0.75) -> dict:
    if not user_agent or "@" not in user_agent:
        raise ValueError("SEC_USER_AGENT contact identifier is required")
    if delay < 0.25:
        raise ValueError("SEC request interval is too short")
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory exists and is nonempty; refusing overwrite")
    targets = selected_targets()
    output.mkdir(parents=True, exist_ok=True)
    issuers = []
    for ticker, cik in targets.items():
        root_name = f"CIK{cik}.json"
        root_url = f"https://data.sec.gov/submissions/{root_name}"
        root_path = output / "raw" / ticker / root_name
        root = fetch_json(root_url, user_agent, root_path, delay)
        if str(root.get("cik", "")).zfill(10) != cik:
            raise ValueError(f"SEC CIK mismatch: {ticker}")
        records = records_from_arrays(root["filings"]["recent"])
        shards = []
        for name in matching_shards(root, START, CUTOFF):
            shard_url = f"https://data.sec.gov/submissions/{name}"
            shard_path = output / "raw" / ticker / name
            shard = fetch_json(shard_url, user_agent, shard_path, delay)
            records.extend(records_from_arrays(shard))
            shards.append({"url": shard_url,
                           "path": str(shard_path.relative_to(output)),
                           "sha256": hashlib.sha256(shard_path.read_bytes()).hexdigest()})
        candidates = []
        for filing in earnings_candidates(records, START, CUTOFF)[:6]:
            accession = filing["accessionNumber"]
            compact = accession.replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                   f"{compact}/{accession}-index.html")
            path = output / "raw" / ticker / f"{accession}-index.html"
            source = fetch_index(url, user_agent, path, delay)
            links = exhibit_urls(source, accession, cik)
            candidates.append({"filing_date": filing["filingDate"],
                               "accession": accession,
                               "index_url": url,
                               "index_path": str(path.relative_to(output)),
                               "index_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "ex99_1_urls": links,
                               "status": "ex99_1_found" if len(links) == 1 else
                                         ("no_ex99_1" if not links else "ambiguous_ex99_1")})
        issuers.append({"ticker": ticker, "cik": cik,
                        "root_index": {"url": root_url,
                                       "path": str(root_path.relative_to(output)),
                                       "sha256": hashlib.sha256(root_path.read_bytes()).hexdigest()},
                        "shard_indexes": shards, "candidate_filings": candidates,
                        "status": "filing_artifacts_found_period_and_basis_unverified"})
        print(f"{ticker}: {len(candidates)} candidate filings; "
              f"{sum(item['status']=='ex99_1_found' for item in candidates)} "
              "single EX-99.1", flush=True)
    manifest = {"version": 2,
                "status": "public_sec_candidate_indexes_archived_no_model_observations",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "v2_frame_sha256": hashlib.sha256(
                    (HERE / "postcorrection_holdout_frame_v2.json").read_bytes()).hexdigest(),
                "filing_start": START, "filing_cutoff": CUTOFF,
                "request_delay_seconds": delay, "issuers": issuers}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    cli.add_argument("--delay", type=float, default=0.75)
    args = cli.parse_args()
    discover(args.output_dir, os.environ.get("SEC_USER_AGENT", ""), args.delay)
