#!/usr/bin/env python3
"""Mask v4 answers for claim-level review without changing raw observations.

This prepares blank score templates; it does not score, call a model, or
turn the 20 selected SEC extracts into a complete-filing gold standard.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
from aggregate_postcorrection_judgments_v2 import verify_frozen_results
from prepare_postcorrection_judgment_v2 import new_masked_id, packet_for_judge
from run_thesis_event_panel import sha256


DIMENSIONS = ("F", "I", "R", "S", "U")


def prepare(results_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    verify_frozen_results(results_dir)
    packets = {}
    for path in (*source_batch.FIRST_PACKETS.values(),
                 *source_batch.DECLARED_PACKETS.values()):
        packet = json.loads(path.read_text())
        if packet["case_id"] in packets:
            raise ValueError("duplicate frozen source case")
        packets[packet["case_id"]] = packet
    if len(packets) != 20:
        raise ValueError("v4 source frame is not 20 cases")
    result_paths = sorted(results_dir.glob("*/result.json"))
    if not result_paths:
        raise ValueError("no observation results")
    results = [json.loads(path.read_text()) for path in result_paths]
    if (len({item["observation_id"] for item in results}) != len(results)
            or any(item["case_id"] not in packets for item in results)):
        raise ValueError("result identifiers do not match frozen v4 case frame")
    output_dir.mkdir(parents=True)
    packet_dir = output_dir / "masked_packets"
    score_dir = output_dir / "scores"
    packet_dir.mkdir()
    score_dir.mkdir()
    mapping = []
    used = set()
    for path, result in zip(result_paths, results):
        mask = new_masked_id()
        if mask in used:
            raise ValueError("masked ID collision")
        used.add(mask)
        item = packet_for_judge(result, packets[result["case_id"]], mask)
        (packet_dir / f"{mask}.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n")
        blank = {
            "masked_id": mask, "reviewer": "",
            "coverage": {"final_answer": False, "persisted_review": False},
            "scores": {name: None for name in DIMENSIONS},
            "claim_adjudications": [], "critical_errors": [],
            "assessable_implication": False, "notes": "",
        }
        (score_dir / f"{mask}.json").write_text(
            json.dumps(blank, indent=2, ensure_ascii=False) + "\n")
        mapping.append({"masked_id": mask,
                        "observation_id": result["observation_id"],
                        "raw_result_path": str(path.resolve()),
                        "raw_result_sha256": sha256(path),
                        "mechanical_status": result.get("status"),
                        "runtime_error": result.get("error"),
                        "estimated_cost_usd": result.get("estimated_cost_usd")})
    (output_dir / "PRIVATE-MAPPING.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "MASKED-PACKET-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output_dir)}\n"
        for path in sorted(packet_dir.glob("*.json"))))
    return {"status": "v4_masked_judgment_inputs_prepared_no_scores",
            "packets": len(mapping), "source_cases": len({x["case_id"] for x in results}),
            "raw_results_changed": False, "new_model_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.results_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
