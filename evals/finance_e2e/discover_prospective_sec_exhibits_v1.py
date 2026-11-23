#!/usr/bin/env python3
"""Archive SEC filing indexes and identify EX-99.1 URLs for frozen candidates."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

from rank_prospective_cross_workflow_v1 import FRAME, ROOT, SEED_SOURCE, rank, verify_identity_snapshot


PARENT = ROOT / "results" / "2026-10-23-prospective-sec-submission-discovery-v1" / "manifest.json"


def exhibit_urls(index_html: str, accession: str, cik: str) -> list[str]:
    compact = accession.replace("-", "")
    prefix = f"/Archives/edgar/data/{int(cik)}/{compact}/"
    output = []
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", index_html,
                          flags=re.IGNORECASE | re.DOTALL):
        if not re.search(r">\s*EX-99\.1\s*<", row, flags=re.IGNORECASE):
            continue
        links = re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", row, flags=re.IGNORECASE)
        for link in links:
            full = urljoin("https://www.sec.gov", html.unescape(link))
            parsed = urlparse(full)
            if parsed.scheme == "https" and parsed.hostname == "www.sec.gov" and parsed.path.startswith(prefix):
                output.append(full)
    return sorted(set(output))


def fetch_index(url: str, user_agent: str, target: Path, delay: float) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "www.sec.gov" or not parsed.path.endswith("-index.html"):
        raise ValueError("only SEC filing-index URLs are permitted")
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
        if not raw or len(raw) > 2_000_000:
            raise RuntimeError(f"SEC filing index empty or unexpectedly large: {url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(raw)
    return raw.decode("utf-8", errors="replace")


def discover(parent: dict, frame: dict, output_dir: Path, user_agent: str, delay: float) -> dict:
    ranked = rank(frame, SEED_SOURCE.read_bytes())
    expected = {ticker for groups in ranked["strata"].values() for ticker in groups["primary"]}
    if {item["ticker"] for item in parent["issuers"]} != expected:
        raise ValueError("parent manifest does not cover every frozen primary issuer")
    if parent["frame_sha256"] != hashlib.sha256(FRAME.read_bytes()).hexdigest():
        raise ValueError("parent discovery used a different frame")
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("contact User-Agent and conservative delay are required")
    if (output_dir / "manifest.json").exists():
        raise ValueError("completed exhibit discovery exists; do not overwrite")
    if output_dir.exists() and any(item.name != "raw" for item in output_dir.iterdir()):
        raise ValueError("output directory contains unexpected files")
    output_dir.mkdir(parents=True, exist_ok=True)
    issuers = []
    for issuer in parent["issuers"]:
        ticker, cik = issuer["ticker"], issuer["cik"]
        candidates = []
        for filing in issuer["earnings_8k_2_02_candidates"]:
            accession = filing["accessionNumber"]
            compact = accession.replace("-", "")
            index_url = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                         f"{compact}/{accession}-index.html")
            target = output_dir / "raw" / ticker / f"{accession}-index.html"
            source = fetch_index(index_url, user_agent, target, delay)
            urls = exhibit_urls(source, accession, cik)
            candidates.append({"filing_date": filing["filingDate"],
                               "accession": accession,
                               "index_url": index_url,
                               "index_path": str(target.relative_to(output_dir)),
                               "index_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                               "ex99_1_urls": urls,
                               "status": "ex99_1_found" if len(urls) == 1 else
                                         ("no_ex99_1" if not urls else "ambiguous_multiple_ex99_1")})
        issuers.append({"ticker": ticker, "cik": cik, "candidates": candidates,
                        "status": "artifact_identity_checked_period_and_fact_audit_pending"})
        found = sum(len(item["ex99_1_urls"]) == 1 for item in candidates)
        print(f"{ticker}: {found}/{len(candidates)} filings have one EX-99.1 artifact", flush=True)
    manifest = {"version": 1, "status": "exhibit_candidates_only_no_model_observations",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "parent_manifest_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
                "frame_sha256": hashlib.sha256(FRAME.read_bytes()).hexdigest(),
                "request_delay_seconds": delay, "issuers": issuers}
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    cli = argparse.ArgumentParser()
    cli.add_argument("--output-dir", required=True, type=Path)
    cli.add_argument("--delay", type=float, default=0.75)
    args = cli.parse_args()
    frame = json.loads(FRAME.read_text(encoding="utf-8"))
    verify_identity_snapshot(frame, (ROOT / frame["issuer_identity_snapshot_path"]).read_bytes())
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    result = discover(parent, frame, args.output_dir, os.environ.get("SEC_USER_AGENT", ""), args.delay)
    print(f"archived {sum(len(item['candidates']) for item in result['issuers'])} SEC filing indexes")
