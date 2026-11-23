#!/usr/bin/env python3
"""Discover only the next frozen same-stratum reserve for an ineligible issuer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import discover_reference_source_frame_v1 as prior
from run_thesis_event_panel import HERE, sha256


FRAME = HERE / "results/2026-10-26-reference-cross-workflow-expansion-frame-v1/FRAME.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replace", required=True, help="frozen planned issuer ruled ineligible")
    parser.add_argument("--delay", type=float, default=1.5)
    args = parser.parse_args()
    if args.delay < 0.75:
        raise ValueError("SEC request delay must be at least 0.75 seconds")
    prior.FRAME = FRAME
    _stratum, reserve = prior.first_reserve_for(json.loads(FRAME.read_text()), args.replace)
    result = prior.discover(args.output_dir, [reserve["ticker"]],
                            os.environ.get("SEC_USER_AGENT", ""), args.delay,
                            reserve_for=args.replace)
    metadata = {"expansion_frame_sha256": sha256(FRAME),
                "replaced_symbol": args.replace, "reserve_symbol": reserve["ticker"],
                "wrapper_sha256": sha256(Path(__file__)),
                "reused_discovery_script_sha256": sha256(Path(prior.__file__)),
                "issuers": len(result["issuers"]), "model_observations": 0}
    (args.output_dir / "EXPANSION-RESERVE-METADATA.json").write_text(
        json.dumps(metadata, indent=2) + "\n")
    files = sorted(path for path in args.output_dir.rglob("*") if path.is_file()
                   and path.name != "RESULT-SHA256.txt")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(args.output_dir)}\n" for path in files))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
