#!/usr/bin/env python3
"""Archive SEC filing-index candidates for source-distinct v4 issuers.

This is public-source discovery only; it neither audits periods/rows nor
contacts a model. The SEC contact User-Agent is never written to output.
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
from verify_postcorrection_unseen_candidates_v4 import ROSTER, verify
import rank_postcorrection_holdout_v2 as v2_rank
from fetch_sources import ROOT


HERE = Path(__file__).parent
START, CUTOFF = "2025-01-01", "2025-12-31"


def discover(output: Path, symbols: list[str], user_agent: str,
             delay: float = 0.75, max_filings: int = 4) -> dict:
    verified = verify()
    roster = json.loads(ROSTER.read_text())
    allowed = {symbol for group in verified["selected_by_stratum"].values()
               for symbol in group}
    if not symbols or len(symbols) != len(set(symbols)) or not set(symbols) <= allowed:
        raise ValueError("symbols must be distinct initial v4 candidates")
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if not 2 <= max_filings <= 6:
        raise ValueError("max_filings must be 2–6")
    if output.exists() and any(item.name != "raw" for item in output.iterdir()):
        raise ValueError("output directory has non-raw files; refusing overwrite")
    snapshot_path = ROOT / json.loads(v2_rank.FRAME.read_text())[
        "issuer_identity_snapshot_path"]
    snapshot = json.loads(snapshot_path.read_text())
    cik_by_ticker = {row[2]: str(row[0]).zfill(10) for row in snapshot["data"]}
    issuers = []
    for symbol in symbols:
        cik = cik_by_ticker[symbol]
        root_name = f"CIK{cik}.json"
        root_url = f"https://data.sec.gov/submissions/{root_name}"
        root_path = output / "raw" / symbol / root_name
        root = fetch_json(root_url, user_agent, root_path, delay)
        if str(root.get("cik", "")).zfill(10) != cik:
            raise ValueError(f"SEC CIK mismatch: {symbol}")
        records = records_from_arrays(root["filings"]["recent"])
        shards = []
        for name in matching_shards(root, START, CUTOFF):
            url = f"https://data.sec.gov/submissions/{name}"
            path = output / "raw" / symbol / name
            shard = fetch_json(url, user_agent, path, delay)
            records.extend(records_from_arrays(shard))
            shards.append({"url": url, "path": str(path.relative_to(output)),
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        candidates = []
        for filing in earnings_candidates(records, START, CUTOFF)[:max_filings]:
            accession = filing["accessionNumber"]
            compact = accession.replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                   f"{compact}/{accession}-index.html")
            path = output / "raw" / symbol / f"{accession}-index.html"
            index = fetch_index(url, user_agent, path, delay)
            exhibits = exhibit_urls(index, accession, cik)
            candidates.append({"filing_date": filing["filingDate"],
                               "accession": accession, "index_url": url,
                               "index_path": str(path.relative_to(output)),
                               "index_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                               "ex99_1_urls": exhibits,
                               "status": "one_ex99_1" if len(exhibits) == 1 else
                                         "no_ex99_1" if not exhibits else
                                         "ambiguous_ex99_1"})
        issuers.append({"symbol": symbol, "cik": cik,
                        "submissions_url": root_url,
                        "submissions_path": str(root_path.relative_to(output)),
                        "submissions_sha256": hashlib.sha256(root_path.read_bytes()).hexdigest(),
                        "shards": shards, "candidate_filings": candidates,
                        "status": "filing_artifacts_only_period_basis_and_facts_unverified"})
        print(f"{symbol}: {len(candidates)} Item 2.02 filings, "
              f"{sum(c['status']=='one_ex99_1' for c in candidates)} single EX-99.1",
              flush=True)
    manifest = {
        "version": 4,
        "status": "public_sec_candidate_indexes_archived_no_model_observations",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_roster_sha256": hashlib.sha256(ROSTER.read_bytes()).hexdigest(),
        "filing_start": START, "filing_cutoff": CUTOFF,
        "request_delay_seconds": delay,
        "max_filings_per_issuer": max_filings,
        "model_observations": 0,
        "issuers": issuers,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output-dir", type=Path, required=True)
    cli.add_argument("--symbols", required=True, help="comma-separated initial candidates")
    cli.add_argument("--delay", type=float, default=0.75)
    cli.add_argument("--max-filings", type=int, default=4)
    args = cli.parse_args()
    result = discover(args.output_dir, args.symbols.split(","),
                      os.environ.get("SEC_USER_AGENT", ""), args.delay,
                      args.max_filings)
    print(json.dumps({"issuers": len(result["issuers"]),
                      "model_observations": 0}, indent=2))
