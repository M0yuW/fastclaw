#!/usr/bin/env python3
"""Freeze all SEC EX-99-family candidates per period from a discovery manifest.

This archives bytes and provenance only. It does not qualify the documents as
the intended quarter, audit numeric rows, or contact a model provider.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from build_reference_source_distinct_frame_v1 import sha256
from discover_reference_source_frame_v1 import WINDOWS


MAX_BYTES = 12_000_000


def validate_candidate(issuer: dict, period: str, item: dict) -> tuple[str, str]:
    if period not in WINDOWS or item.get("status") != "one_ex99_candidate":
        raise ValueError("period has no unique EX-99-family candidate")
    urls = item.get("ex99_candidate_urls")
    if not isinstance(urls, list) or len(urls) != 1:
        raise ValueError("candidate URL count differs")
    url = urls[0]
    parsed = urlparse(url)
    accession = item["accession"]
    expected_prefix = (f"/Archives/edgar/data/{int(issuer['cik'])}/"
                       f"{accession.replace('-', '')}/")
    if (parsed.scheme != "https" or parsed.hostname != "www.sec.gov"
            or not parsed.path.startswith(expected_prefix)
            or parsed.query or parsed.fragment):
        raise ValueError("EX-99 candidate URL differs from SEC accession")
    return url, parsed.path.rsplit("/", 1)[1]


def fetch(url: str, path: Path, user_agent: str, delay: float) -> None:
    if path.exists():
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError(f"cached SEC artifact invalid: {path}")
        return
    curl = shutil.which("curl")
    if curl is None:
        raise RuntimeError("curl is required")
    time.sleep(delay)
    command = [curl, "--fail", "--silent", "--show-error", "--location",
               "--proto", "=https", "--proto-redir", "=https",
               "--connect-timeout", "15", "--max-time", "90", "--retry", "2",
               "--retry-delay", "2", "--retry-all-errors", "--user-agent",
               user_agent, "--header", "Accept-Encoding: identity", url]
    response = subprocess.run(command, capture_output=True, timeout=300)
    if response.returncode:
        raise RuntimeError(f"SEC artifact request failed: {url}: "
                           + response.stderr.decode(errors="replace").strip())
    if not 0 < len(response.stdout) <= MAX_BYTES:
        raise RuntimeError(f"SEC artifact empty or too large: {url}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(response.stdout)


def freeze(discovery_path: Path, output: Path, user_agent: str,
           delay: float = 0.75) -> dict:
    if not user_agent or "@" not in user_agent or delay < 0.25:
        raise ValueError("SEC contact User-Agent and conservative delay required")
    if output.exists() and any(item.name != "raw" for item in output.iterdir()):
        raise ValueError("output directory contains unexpected files")
    discovery = json.loads(discovery_path.read_text())
    if discovery.get("status") != "public_sec_index_discovery_no_model_observations":
        raise ValueError("discovery manifest status differs")
    frozen = []
    for issuer in discovery["issuers"]:
        for period in WINDOWS:
            candidates = issuer["windows"][period]["candidates"]
            if not candidates:
                raise ValueError(f"no candidate for {issuer['symbol']} {period}")
            for candidate in candidates:
                url, filename = validate_candidate(issuer, period, candidate)
                path = (output / "raw" / issuer["symbol"] / period
                        / candidate["accession"] / filename)
                fetch(url, path, user_agent, delay)
                frozen.append({"symbol": issuer["symbol"], "period_window": period,
                               "filing_date": candidate["filing_date"],
                               "accession": candidate["accession"], "url": url,
                               "path": str(path.relative_to(output)),
                               "sha256": sha256(path), "bytes": path.stat().st_size,
                               "status": "artifact_frozen_period_and_rows_unverified"})
                print(f"{issuer['symbol']} {period} {candidate['accession']}: "
                      f"{path.stat().st_size} bytes", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1,
                "status": "sec_exhibits_frozen_period_and_rows_unverified",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "discovery_manifest_sha256": sha256(discovery_path),
                "freeze_script_sha256": sha256(Path(__file__)),
                "request_delay_seconds": delay,
                "model_observations": 0, "artifacts": frozen}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = sorted(path for path in output.rglob("*") if path.is_file()
                   and path.name != "RESULT-SHA256.txt")
    (output / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output)}\n" for path in files))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discovery-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=0.75)
    args = parser.parse_args()
    result = freeze(args.discovery_manifest, args.output_dir,
                    os.environ.get("SEC_USER_AGENT", ""), args.delay)
    print(json.dumps({"frozen_artifacts": len(result["artifacts"]),
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
