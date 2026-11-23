#!/usr/bin/env python3
"""Archive SEC filing candidates for the frozen source-distinct issuer frame.

Public-source discovery only: an EX-99.1 link is not a qualified quarter pair,
an audited fact packet, a model observation, or an insight-quality score.
The contact User-Agent is sent to SEC but never included in output artifacts.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from build_reference_source_distinct_frame_v1 import sha256
from discover_prospective_sec_exhibits_v1 import fetch_index
from discover_prospective_sec_submissions_v1 import (
    earnings_candidates, fetch_json, matching_shards, records_from_arrays,
)


HERE = Path(__file__).parent
FRAME = HERE / "results/2026-10-25-reference-source-distinct-frame-v2/FRAME.json"
WINDOWS = {
    "CY2025_Q2": ("2025-07-01", "2025-09-30"),
    "CY2025_Q3": ("2025-10-01", "2025-12-31"),
}
MAX_INDEXES_PER_WINDOW = 3


def earnings_exhibit_urls(index_html: str, accession: str, cik: str) -> list[str]:
    """Find SEC-hosted EX-99, EX-99.1, or EX-99.01 candidates only."""
    prefix = f"/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/"
    found = set()
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", index_html,
                          flags=re.IGNORECASE | re.DOTALL):
        if not re.search(r">\s*EX-99(?:\.0?1)?\s*<", row,
                         flags=re.IGNORECASE):
            continue
        for link in re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", row,
                               flags=re.IGNORECASE):
            full = urljoin("https://www.sec.gov", html.unescape(link))
            parsed = urlparse(full)
            if (parsed.scheme == "https" and parsed.hostname == "www.sec.gov"
                    and parsed.path.startswith(prefix)):
                found.add(full)
    return sorted(found)


def planned(frame: dict) -> dict:
    return {entry["ticker"]: (stratum, entry)
            for stratum, group in frame["strata"].items()
            for entry in group["planned"]}


def first_reserve_for(frame: dict, replaced_symbol: str) -> tuple[str, dict]:
    for stratum, group in frame["strata"].items():
        if any(item["ticker"] == replaced_symbol for item in group["planned"]):
            if not group["reserves_in_order"]:
                raise ValueError("stratum has no frozen reserve")
            return stratum, group["reserves_in_order"][0]
    raise ValueError("replacement target is not a planned issuer")


def select_candidates(records: list[dict]) -> dict:
    output = {}
    for period, (start, end) in WINDOWS.items():
        found = earnings_candidates(records, start, end)
        output[period] = {
            "total_item_2_02_filings_in_window": len(found),
            "selected_filings": found[:MAX_INDEXES_PER_WINDOW],
            "truncated": len(found) > MAX_INDEXES_PER_WINDOW,
        }
    return output


def discover(output: Path, symbols: list[str], user_agent: str,
             delay: float = 0.75, reserve_for: str | None = None) -> dict:
    frame = json.loads(FRAME.read_text())
    if reserve_for is None:
        allowed = planned(frame)
    else:
        stratum, entry = first_reserve_for(frame, reserve_for)
        allowed = {entry["ticker"]: (stratum, entry)}
        if symbols != [entry["ticker"]]:
            raise ValueError("only the next frozen same-stratum reserve is eligible")
    if not symbols or len(symbols) != len(set(symbols)) or not set(symbols) <= set(allowed):
        raise ValueError("symbols must be distinct planned frame issuers")
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if (output / "manifest.json").exists():
        raise ValueError("completed manifest exists; refusing overwrite")
    if output.exists() and any(item.name != "raw" for item in output.iterdir()):
        raise ValueError("output directory contains unexpected files")
    start, cutoff = min(pair[0] for pair in WINDOWS.values()), max(
        pair[1] for pair in WINDOWS.values())
    issuers = []
    for symbol in symbols:
        stratum, entry = allowed[symbol]
        cik = str(entry["cik"]).zfill(10)
        root_name = f"CIK{cik}.json"
        root_url = f"https://data.sec.gov/submissions/{root_name}"
        root_path = output / "raw" / symbol / root_name
        root = fetch_json(root_url, user_agent, root_path, delay)
        if str(root.get("cik", "")).zfill(10) != cik:
            raise ValueError(f"SEC CIK differs from frozen frame: {symbol}")
        records = records_from_arrays(root["filings"]["recent"])
        shards = []
        for name in matching_shards(root, start, cutoff):
            url = f"https://data.sec.gov/submissions/{name}"
            path = output / "raw" / symbol / name
            shard = fetch_json(url, user_agent, path, delay)
            records.extend(records_from_arrays(shard))
            shards.append({"url": url, "path": str(path.relative_to(output)),
                           "sha256": sha256(path)})
        windows = select_candidates(records)
        for period, group in windows.items():
            candidates = []
            for filing in group.pop("selected_filings"):
                accession = filing["accessionNumber"]
                url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                       f"{accession.replace('-', '')}/{accession}-index.html")
                path = output / "raw" / symbol / f"{accession}-index.html"
                index = fetch_index(url, user_agent, path, delay)
                links = earnings_exhibit_urls(index, accession, cik)
                candidates.append({"filing_date": filing["filingDate"],
                                   "accession": accession, "index_url": url,
                                   "index_path": str(path.relative_to(output)),
                                   "index_sha256": sha256(path),
                                   "ex99_candidate_urls": links,
                                   "status": "one_ex99_candidate" if len(links) == 1 else
                                             "no_ex99_candidate" if not links else
                                             "ambiguous_ex99_candidates"})
            group["candidates"] = candidates
            print(f"{symbol} {period}: {len(candidates)} indexes, "
                  f"{sum(item['status'] == 'one_ex99_candidate' for item in candidates)} "
                  "single EX-99-family candidate", flush=True)
        issuers.append({"symbol": symbol, "cik": cik, "stratum": stratum,
                        "frozen_rank_sha256": entry["rank_sha256"],
                        "submissions": {"url": root_url,
                                        "path": str(root_path.relative_to(output)),
                                        "sha256": sha256(root_path)},
                        "shards": shards, "windows": windows,
                        "status": "filing_candidates_only_period_and_rows_unverified"})
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": 1,
        "status": "public_sec_index_discovery_no_model_observations",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frame_sha256": sha256(FRAME),
        "discovery_script_sha256": sha256(Path(__file__)),
        "windows": WINDOWS,
        "max_indexes_per_window": MAX_INDEXES_PER_WINDOW,
        "request_delay_seconds": delay,
        "reserve_replaces": reserve_for,
        "model_observations": 0,
        "issuers": issuers,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = sorted(path for path in output.rglob("*") if path.is_file()
                   and path.name != "RESULT-SHA256.txt")
    (output / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output)}\n" for path in files))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--symbols", required=True,
                        help="comma-separated planned issuers in frozen frame")
    parser.add_argument("--delay", type=float, default=0.75)
    parser.add_argument("--reserve-for", help="planned issuer disqualified by source-period audit")
    args = parser.parse_args()
    result = discover(args.output_dir, args.symbols.split(","),
                      os.environ.get("SEC_USER_AGENT", ""), args.delay,
                      args.reserve_for)
    print(json.dumps({"issuers": len(result["issuers"]),
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
