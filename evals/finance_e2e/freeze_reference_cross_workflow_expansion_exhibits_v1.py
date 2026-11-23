#!/usr/bin/env python3
"""Archive all EX-99 candidates for the thirty additional issuer slots.

Reuse the three already frozen pilot/reserve archives by URL. Preserve every
candidate in ambiguous filing windows for later period/content review.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from freeze_reference_source_exhibits_v1 import fetch, validate_candidate
from run_thesis_event_panel import HERE, sha256


RESULTS = HERE / "results"
FRAME = RESULTS / "2026-10-26-reference-cross-workflow-expansion-frame-v1/FRAME.json"
DISCOVERIES = [
    "2026-10-26-reference-cross-workflow-expansion-discovery-pilot-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-regional-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-payments-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-capital-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-data-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-alit-reserve-v1",
    "2026-10-26-reference-cross-workflow-expansion-discovery-rf-reserve-v1",
]
CACHED_EXHIBITS = [
    "2026-10-26-reference-cross-workflow-expansion-exhibits-pilot-v1",
    "2026-10-26-reference-cross-workflow-expansion-exhibits-alit-reserve-v1",
    "2026-10-26-reference-cross-workflow-expansion-exhibits-rf-reserve-v1",
]
EXCLUDED = {"INTU": "fiscal_period_pair_not_CY2025_Q2_Q3",
            "OZK": "no_item_2_02_candidate_in_either_window"}


def verified_manifest(directory: Path) -> dict:
    checks = {}
    for line in (directory / "RESULT-SHA256.txt").read_text().splitlines():
        digest, relative = line.split(maxsplit=1)
        path = directory / relative.strip()
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"source archive hash mismatch: {path}")
        checks[relative.strip()] = digest
    if "manifest.json" not in checks:
        raise ValueError("archive manifest absent from hash list")
    return json.loads((directory / "manifest.json").read_text())


def cached_sources() -> dict[str, tuple[Path, str]]:
    cache = {}
    for name in CACHED_EXHIBITS:
        directory = RESULTS / name
        manifest = verified_manifest(directory)
        for item in manifest["artifacts"]:
            path = directory / item["path"]
            if item["url"] in cache or sha256(path) != item["sha256"]:
                raise ValueError("duplicate or altered cached SEC exhibit")
            cache[item["url"]] = path, item["sha256"]
    return cache


def freeze(output: Path, user_agent: str, delay: float) -> dict:
    if "@" not in user_agent or delay < 0.75:
        raise ValueError("declared SEC contact and >=0.75 second delay required")
    if output.exists() and any(path.name != "raw" for path in output.iterdir()):
        raise ValueError("output contains finalized or unexpected files")
    frame = json.loads(FRAME.read_text())
    planned = {entry["ticker"] for group in frame["strata"].values()
               for entry in group["planned"]}
    target = (planned - set(EXCLUDED)) | {"ALIT", "RF"}
    if len(target) != 30:
        raise ValueError("source-disjoint target count differs")
    cache = cached_sources()
    issuers, manifest_hashes = {}, {}
    for name in DISCOVERIES:
        directory = RESULTS / name
        discovery = verified_manifest(directory)
        if discovery["frame_sha256"] != sha256(FRAME):
            raise ValueError("discovery frame hash differs")
        manifest_hashes[name] = sha256(directory / "manifest.json")
        for issuer in discovery["issuers"]:
            symbol = issuer["symbol"]
            if symbol in issuers:
                raise ValueError(f"duplicate discovered issuer: {symbol}")
            issuers[symbol] = issuer
    if set(issuers) != planned | {"ALIT", "RF"}:
        raise ValueError("discovery issuer coverage differs")
    artifacts = []
    for symbol in sorted(target):
        issuer = issuers[symbol]
        for period in ("CY2025_Q2", "CY2025_Q3"):
            candidates = [item for item in issuer["windows"][period]["candidates"]
                          if item["status"] == "one_ex99_candidate"]
            if not candidates:
                raise ValueError(f"no EX-99 candidate: {symbol} {period}")
            for item in candidates:
                url, filename = validate_candidate(issuer, period, item)
                path = output / "raw" / symbol / period / item["accession"] / filename
                if url in cache and not path.exists():
                    old, digest = cache[url]
                    if sha256(old) != digest:
                        raise ValueError("cached source changed")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old, path)
                else:
                    fetch(url, path, user_agent, delay)
                artifacts.append({"symbol": symbol, "period_window": period,
                                  "filing_date": item["filing_date"],
                                  "accession": item["accession"], "url": url,
                                  "path": str(path.relative_to(output)),
                                  "sha256": sha256(path), "bytes": path.stat().st_size,
                                  "reused_existing_freeze": url in cache,
                                  "status": "artifact_frozen_period_and_rows_unverified"})
                print(f"{symbol} {period} {item['accession']}: "
                      f"{path.stat().st_size} bytes", flush=True)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"version": 1,
                "status": "cross_workflow_expansion_exhibits_frozen_unqualified",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "frame_sha256": sha256(FRAME),
                "discovery_manifest_sha256": manifest_hashes,
                "freeze_script_sha256": sha256(Path(__file__)),
                "excluded_before_source_row_audit": EXCLUDED,
                "target_issuers": len(target),
                "artifact_count": len(artifacts),
                "model_observations": 0, "artifacts": artifacts}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = sorted(path for path in output.rglob("*") if path.is_file()
                   and path.name != "RESULT-SHA256.txt")
    (output / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output)}\n" for path in files))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    result = freeze(args.output_dir, os.environ.get("SEC_USER_AGENT", ""), args.delay)
    print(json.dumps({"target_issuers": result["target_issuers"],
                      "artifacts": result["artifact_count"],
                      "model_observations": 0}, indent=2))


if __name__ == "__main__":
    main()
