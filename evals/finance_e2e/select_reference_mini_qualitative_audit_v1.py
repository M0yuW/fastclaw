#!/usr/bin/env python3
"""Freeze four previously unscored SEC observations without reading answers.

The selection is response-blind and covers four different issuers, but earlier
observations from those issuers may have been reviewed. It is a small case
study, not an issuer-independent holdout or a reliability-rate sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import blank_template, verify_frozen_results
from aggregate_reference_source_distinct_judgments_v1 import verify_masked_packet_hashes
from run_thesis_event_panel import HERE, sha256


RESULTS = HERE / "results/2026-10-26-reference-source-distinct-insight-flash-v1"
JUDGMENTS = HERE / "results/2026-10-26-reference-source-distinct-insight-judgment-v1"
SEED = "reference-mini-qualitative-case-study-2026-10-27-v1"
SAMPLE_SIZE = 4


def select() -> dict:
    verify_frozen_results(RESULTS)
    mapping = json.loads((JUDGMENTS / "PRIVATE-MAPPING.json").read_text())
    if len(mapping) != 150 or len({m["masked_id"] for m in mapping}) != 150:
        raise ValueError("expected 150 unique masked observations")
    verify_masked_packet_hashes(JUDGMENTS, {m["masked_id"] for m in mapping})
    eligible = []
    for entry in mapping:
        mask = entry["masked_id"]
        score = json.loads((JUDGMENTS / "scores" / f"{mask}.json").read_text())
        if blank_template(score, mask):
            observation_id = entry["observation_id"]
            symbol = observation_id.split("-", 3)[1]
            rank = hashlib.sha256(f"{SEED}:{mask}".encode()).hexdigest()
            eligible.append((rank, symbol, mask, observation_id))
    if len(eligible) != 50:
        raise ValueError("expected 50 untouched masked score templates")
    chosen = []
    seen_symbols = set()
    for rank, symbol, mask, observation_id in sorted(eligible):
        if symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        chosen.append({"masked_id": mask, "selection_rank_sha256": rank})
        if len(chosen) == SAMPLE_SIZE:
            break
    if len(chosen) != SAMPLE_SIZE:
        raise ValueError("insufficient distinct issuers")
    return {
        "status": "selected_before_reading_four_answers",
        "seed": SEED,
        "eligible_unscored_observations": len(eligible),
        "selected_observations": len(chosen),
        "distinct_issuer_constraint": True,
        "selected_masked_ids": chosen,
        "claim_limit": (
            "Response-blind mini case study only. Earlier runs from the same issuers may "
            "have been judged; the reviewer is not independent of prior work. Do not "
            "infer a population quality rate or call this an issuer-level holdout."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    result = select()
    args.output_dir.mkdir(parents=True)
    selection_path = args.output_dir / "SELECTION.json"
    selection_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "frozen_result_hash_list_sha256": sha256(RESULTS / "RESULT-SHA256.txt"),
        "masked_packet_hash_list_sha256": sha256(JUDGMENTS / "MASKED-PACKET-SHA256.txt"),
        "private_mapping_sha256": sha256(JUDGMENTS / "PRIVATE-MAPPING.json"),
        "selection_script_sha256": sha256(Path(__file__)),
    }
    manifest_path = args.output_dir / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        "".join(f"{sha256(args.output_dir / name)}  {name}\n"
                for name in ("MANIFEST.json", "SELECTION.json")))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
