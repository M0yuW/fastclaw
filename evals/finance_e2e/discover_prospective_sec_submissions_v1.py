#!/usr/bin/env python3
"""Archive public SEC submission indexes for the pre-ranked issuer frame.

This finds filing *candidates*, not eligible fiscal-quarter pairs or audited
facts. It never calls a model or changes the frozen issuer selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from rank_prospective_cross_workflow_v1 import FRAME, ROOT, SEED_SOURCE, rank, verify_identity_snapshot


def records_from_arrays(arrays: dict) -> list[dict]:
    fields = ("accessionNumber", "filingDate", "form", "items", "primaryDocument")
    if not all(isinstance(arrays.get(field), list) for field in fields):
        raise ValueError("SEC submissions arrays are incomplete")
    count = len(arrays["form"])
    if any(len(arrays[field]) != count for field in fields):
        raise ValueError("SEC submissions arrays have inconsistent lengths")
    return [{field: arrays[field][i] for field in fields} for i in range(count)]


def matching_shards(root: dict, start: str, cutoff: str) -> list[str]:
    return [item["name"] for item in root.get("filings", {}).get("files", [])
            if item["filingFrom"] <= cutoff and item["filingTo"] >= start]


def earnings_candidates(records: list[dict], start: str, cutoff: str) -> list[dict]:
    seen = set()
    output = []
    for record in sorted(records, key=lambda item: (item["filingDate"], item["accessionNumber"]),
                         reverse=True):
        if not (start <= record["filingDate"] <= cutoff):
            continue
        if record["form"] not in {"8-K", "8-K/A"}:
            continue
        items = {item.strip() for item in (record.get("items") or "").split(",")}
        if "2.02" not in items:
            continue
        accession = record["accessionNumber"]
        if accession not in seen:
            seen.add(accession)
            output.append(record)
    return output


def fetch_json(url: str, user_agent: str, target: Path, delay: float) -> dict:
    if not url.startswith("https://data.sec.gov/submissions/"):
        raise ValueError("only SEC submissions URLs are permitted")
    if target.exists():
        raw = target.read_bytes()
    else:
        curl = shutil.which("curl")
        if curl is None:
            raise RuntimeError("curl is required")
        time.sleep(delay)
        command = [curl, "--fail", "--silent", "--show-error", "--location",
                   "--proto", "=https", "--proto-redir", "=https",
                   "--connect-timeout", "15", "--max-time", "60",
                   "--retry", "2", "--retry-delay", "2", "--retry-all-errors",
                   "--user-agent", user_agent, "--header", "Accept-Encoding: identity", url]
        result = subprocess.run(command, capture_output=True, timeout=210)
        if result.returncode:
            raise RuntimeError(f"SEC request failed for {url}: {result.stderr.decode(errors='replace').strip()}")
        raw = result.stdout
        if not raw or len(raw) > 15_000_000:
            raise RuntimeError(f"SEC response empty or unexpectedly large: {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(raw)
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"SEC response is not a JSON object: {url}")
    return payload


def discover(frame: dict, output_dir: Path, user_agent: str, tickers: list[str],
             start: str, delay: float) -> dict:
    ranked = rank(frame, SEED_SOURCE.read_bytes())
    expected = {ticker: (stratum, position)
                for stratum, groups in ranked["strata"].items()
                for position, ticker in enumerate(groups["primary"], 1)}
    if len(tickers) != len(set(tickers)) or any(ticker not in expected for ticker in tickers):
        raise ValueError("tickers must be unique primary candidates in the frozen frame")
    if not user_agent or "@" not in user_agent:
        raise ValueError("SEC_USER_AGENT must contain the supplied contact address")
    if delay < 0.25:
        raise ValueError("delay below conservative SEC request interval")
    if (output_dir / "manifest.json").exists():
        raise ValueError("completed discovery manifest exists; do not overwrite it")
    if output_dir.exists() and any(item.name != "raw" for item in output_dir.iterdir()):
        raise ValueError("output directory contains unexpected files")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for ticker in tickers:
        stratum, position = expected[ticker]
        cik = frame["cik_by_ticker"][ticker]
        root_name = f"CIK{cik}.json"
        root_url = f"https://data.sec.gov/submissions/{root_name}"
        root_path = output_dir / "raw" / ticker / root_name
        root = fetch_json(root_url, user_agent, root_path, delay)
        if str(root.get("cik", "")).zfill(10) != cik:
            raise ValueError(f"SEC submissions CIK mismatch: {ticker}")
        records = records_from_arrays(root["filings"]["recent"])
        shard_entries = []
        for name in matching_shards(root, start, frame["filing_cutoff"]):
            shard_url = f"https://data.sec.gov/submissions/{name}"
            path = output_dir / "raw" / ticker / name
            shard = fetch_json(shard_url, user_agent, path, delay)
            records.extend(records_from_arrays(shard))
            shard_entries.append({"url": shard_url, "path": str(path.relative_to(output_dir)),
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        candidates = earnings_candidates(records, start, frame["filing_cutoff"])
        results.append({"ticker": ticker, "cik": cik, "stratum": stratum, "primary_rank": position,
                        "root_index": {"url": root_url,
                                       "path": str(root_path.relative_to(output_dir)),
                                       "sha256": hashlib.sha256(root_path.read_bytes()).hexdigest()},
                        "shard_indexes": shard_entries,
                        "earnings_8k_2_02_candidates": candidates,
                        "status": "filing_candidates_only_exhibit_and_period_unverified"})
        print(f"{ticker}: {len(candidates)} Item 2.02 filing candidates; {len(shard_entries)} shards", flush=True)
    manifest = {"version": 1, "status": "filing_candidates_only_no_model_observations",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "frame_sha256": hashlib.sha256(FRAME.read_bytes()).hexdigest(),
                "filing_start": start, "filing_cutoff": frame["filing_cutoff"],
                "request_delay_seconds": delay,
                "issuers": results}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--tickers", required=True, help="comma-separated frozen primary tickers")
    cli.add_argument("--output-dir", required=True, type=Path)
    cli.add_argument("--start", default="2025-01-01")
    cli.add_argument("--delay", type=float, default=0.75)
    args = cli.parse_args()
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    verify_identity_snapshot(frame, (ROOT / frame["issuer_identity_snapshot_path"]).read_bytes())
    manifest = discover(frame, args.output_dir, os.environ.get("SEC_USER_AGENT", ""),
                        args.tickers.split(","), args.start, args.delay)
    print(f"archived {len(manifest['issuers'])} issuer candidate indexes")
