#!/usr/bin/env python3
"""Public SEC discovery for the frozen cross-workflow expansion frame."""

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
    parser.add_argument("--symbols", required=True, help="comma-separated planned issuers")
    parser.add_argument("--delay", type=float, default=0.75)
    args = parser.parse_args()
    if not FRAME.is_file() or args.delay < 0.75:
        raise ValueError("frozen frame and a delay of at least 0.75 seconds required")
    # The imported discovery code applies the same Q2/Q3 filing windows and
    # source-index controls; only its frame path is rebound before any fetch.
    prior.FRAME = FRAME
    result = prior.discover(args.output_dir, args.symbols.split(","),
                            os.environ.get("SEC_USER_AGENT", ""), args.delay)
    metadata = {"expansion_frame_sha256": sha256(FRAME),
                "discovery_wrapper_sha256": sha256(Path(__file__)),
                "reused_discovery_script_sha256": sha256(Path(prior.__file__)),
                "issuers": len(result["issuers"]), "model_observations": 0}
    (args.output_dir / "EXPANSION-METADATA.json").write_text(
        json.dumps(metadata, indent=2) + "\n")
    files = sorted(path for path in args.output_dir.rglob("*") if path.is_file()
                   and path.name != "RESULT-SHA256.txt")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(args.output_dir)}\n" for path in files))
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
