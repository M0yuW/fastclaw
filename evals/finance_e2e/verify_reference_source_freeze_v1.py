#!/usr/bin/env python3
"""Verify the source/case-sheet freeze without model calls or mutation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_reference_source_distinct_frame_v1 import sha256
from preflight_reference_case_criticals_v1 import inspect as case_inspect
from preflight_reference_source_confirmation_v1 import inspect as source_inspect
from run_thesis_event_panel import HERE


MANIFEST = HERE / "results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json"
FILE_PATHS = {
    "frame": "results/2026-10-25-reference-source-distinct-frame-v2/FRAME.json",
    "selection": "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json",
    "case_sheet": "REFERENCE-SOURCE-DISTINCT-CASE-CRITICALS-DRAFT-v1.md",
    "rubric_reference": "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
}


def verify(path: Path = MANIFEST) -> dict:
    manifest = json.loads(path.read_text())
    if (manifest.get("version") != 1 or manifest.get("model_observations") != 0
            or manifest.get("insight_quality_pass") is not None
            or manifest.get("paid_run_authorized") is not False):
        raise ValueError("freeze status invalid")
    if set(manifest["files"]) != set(FILE_PATHS):
        raise ValueError("freeze file set differs")
    for label, expected_path in FILE_PATHS.items():
        item = manifest["files"][label]
        if item["path"] != expected_path or sha256(HERE / expected_path) != item["sha256"]:
            raise ValueError(f"frozen file differs: {label}")
    source = source_inspect()
    case = case_inspect()
    if not source["ready"] or case["issuer_count"] != 30:
        raise ValueError("source or case-sheet preflight not ready")
    checked = {item["symbol"]: item for item in source["generic_verified"]}
    if set(manifest["packets"]) != set(checked):
        raise ValueError("packet membership differs")
    for symbol, item in manifest["packets"].items():
        expected_path = f"{symbol.lower()}_reference_source_row_audit_v{2 if symbol == 'BOKF' else 1}.json"
        observed = checked[symbol]
        if (item["path"] != expected_path
                or sha256(HERE / expected_path) != item["sha256"]
                or item["sha256"] != observed["packet_sha256"]
                or item["comparable"] != observed["comparable_rows"]
                or item["event_only"] != observed["event_only_rows"]
                or item["baseline_only"] != observed["baseline_only_rows"]):
            raise ValueError(f"frozen packet differs: {symbol}")
    counts = {
        "issuers": len(checked),
        "sec_exhibits": 2 * len(checked),
        "comparable_rows": sum(x["comparable_rows"] for x in checked.values()),
        "event_only_rows": sum(x["event_only_rows"] for x in checked.values()),
        "baseline_only_rows": sum(x["baseline_only_rows"] for x in checked.values()),
    }
    if manifest["counts"] != counts:
        raise ValueError("frozen aggregate counts differ")
    return {
        "status": "source_and_case_sheet_freeze_verified_not_model_quality",
        "manifest_sha256": sha256(path),
        "counts": counts,
        "source_ready": True,
        "case_sheet_coverage_ready": True,
        "model_observations": 0,
        "paid_run_authorized": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    print(json.dumps(verify(args.manifest), indent=2))


if __name__ == "__main__":
    main()
