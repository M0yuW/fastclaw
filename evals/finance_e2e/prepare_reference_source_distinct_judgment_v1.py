#!/usr/bin/env python3
"""Prepare outcome-masked, source-linked review packets for the 30-case arm.

This never scores an answer, contacts a model, or modifies raw observations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import verify_frozen_results
from build_reference_source_distinct_event_fixtures_v1 import FREEZE, preflight
from prepare_postcorrection_judgment_v2 import new_masked_id, packet_for_judge
from run_thesis_event_panel import HERE, sha256


DIMENSIONS = ("F", "I", "R", "S", "U")


def prepare(results_dir: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    verify_frozen_results(results_dir)
    prepared = preflight()
    run_ids = set(prepared["run_order"])
    frozen = json.loads(FREEZE.read_text())
    source_packets = {}
    for symbol, item in frozen["packets"].items():
        packet = json.loads((HERE / item["path"]).read_text())
        case_id = f"RS-{symbol}-CY2025Q2Q3"
        if packet["symbol"] != symbol or case_id in source_packets:
            raise ValueError("source packet identity differs")
        source_packets[case_id] = packet
    if len(source_packets) != 30:
        raise ValueError("qualified source frame is not 30 issuer packets")
    result_paths = sorted(results_dir.glob("*/result.json"))
    if not result_paths:
        raise ValueError("no observation results")
    results = [json.loads(path.read_text()) for path in result_paths]
    ids = [result.get("observation_id") for result in results]
    if (len(ids) != len(set(ids)) or not set(ids) <= run_ids
            or any(result.get("case_id") not in source_packets for result in results)
            or any(result["observation_id"] !=
                   f"{result['case_id']}-r{result['repetition']}" for result in results)):
        raise ValueError("results do not match the frozen 30 by five order")
    output_dir.mkdir(parents=True)
    packets_dir, scores_dir = output_dir / "masked_packets", output_dir / "scores"
    packets_dir.mkdir()
    scores_dir.mkdir()
    mapping = []
    for path, result in zip(result_paths, results):
        masked_id = new_masked_id()
        item = packet_for_judge(result, source_packets[result["case_id"]], masked_id)
        (packets_dir / f"{masked_id}.json").write_text(
            json.dumps(item, indent=2, ensure_ascii=False) + "\n")
        blank = {
            "masked_id": masked_id, "reviewer": "",
            "coverage": {"final_answer": False, "persisted_review": False},
            "scores": {name: None for name in DIMENSIONS},
            "claim_adjudications": [], "critical_errors": [],
            "assessable_implication": False, "notes": "",
        }
        (scores_dir / f"{masked_id}.json").write_text(
            json.dumps(blank, indent=2, ensure_ascii=False) + "\n")
        mapping.append({
            "masked_id": masked_id,
            "observation_id": result["observation_id"],
            "raw_result_path": str(path.resolve()),
            "raw_result_sha256": sha256(path),
            "mechanical_status": result.get("status"),
            "runtime_error": result.get("error"),
            "estimated_cost_usd": result.get("estimated_cost_usd"),
        })
    (output_dir / "PRIVATE-MAPPING.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False) + "\n")
    (output_dir / "MASKED-PACKET-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output_dir)}\n"
        for path in sorted(packets_dir.glob("*.json"))))
    return {"status": "source_distinct_masked_inputs_prepared_no_scores",
            "packets": len(mapping),
            "source_cases": len({result["case_id"] for result in results}),
            "raw_results_changed": False, "new_model_calls": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.results_dir, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
