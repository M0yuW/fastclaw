#!/usr/bin/env python3
"""Aggregate reviewed 30-issuer clusters without scoring answers in code."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from aggregate_postcorrection_judgments_v2 import (
    blank_template, one_sided_exact_lower, validate_review,
    verify_frozen_results,
)
from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_thesis_event_panel import sha256


EXPECTED_CASES = 30
REPEATS_PER_CASE = 5


def cluster_gate(observations: list[dict]) -> dict:
    labels = Counter(item["qualitative_label"] for item in observations)
    complete = len(observations) == REPEATS_PER_CASE
    passed = (complete
              and all(item["mechanical_pass"] and item["contract_pass"]
                      and item["critical_error_count"] == 0 for item in observations)
              and labels["high"] >= 4 and labels["adequate"] <= 1
              and labels["problematic"] == labels["not_assessable"] == 0)
    return {"observation_count": len(observations),
            "labels": dict(labels), "gate_pass": passed}


def verify_masked_packet_hashes(judgment_dir: Path, masked_ids: set[str]) -> None:
    path = judgment_dir / "MASKED-PACKET-SHA256.txt"
    if not path.is_file():
        raise ValueError("masked packet hash list missing")
    listed = {}
    for line in path.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        relative = Path(relative)
        if (len(digest) != 64 or relative.is_absolute() or ".." in relative.parts
                or relative in listed):
            raise ValueError("invalid masked packet hash entry")
        listed[relative] = digest
    expected = {Path("masked_packets") / f"{mask}.json" for mask in masked_ids}
    if set(listed) != expected:
        raise ValueError("masked packet list incomplete or has extras")
    for relative, digest in listed.items():
        if sha256(judgment_dir / relative) != digest:
            raise ValueError(f"masked packet hash mismatch: {relative}")


def aggregate(results_dir: Path, judgment_dir: Path) -> dict:
    verify_frozen_results(results_dir)
    prepared = preflight()
    planned = set(prepared["run_order"])
    mapping = json.loads((judgment_dir / "PRIVATE-MAPPING.json").read_text())
    if not isinstance(mapping, list):
        raise ValueError("private mapping must be an array")
    masks = {item["masked_id"] for item in mapping}
    if len(masks) != len(mapping):
        raise ValueError("duplicate masked IDs")
    verify_masked_packet_hashes(judgment_dir, masks)
    all_result_paths = {path.resolve() for path in results_dir.glob("*/result.json")}
    if len(all_result_paths) != len(mapping):
        raise ValueError("not every result has a masked mapping")
    cases: dict[str, list[dict]] = defaultdict(list)
    unreviewed = []
    observed_ids = set()
    for entry in mapping:
        raw = Path(entry["raw_result_path"])
        if raw.resolve() not in all_result_paths or sha256(raw) != entry["raw_result_sha256"]:
            raise ValueError("mapping points outside or differs from frozen result")
        result = json.loads(raw.read_text())
        observation_id = result["observation_id"]
        if (observation_id != entry["observation_id"] or observation_id not in planned
                or observation_id in observed_ids):
            raise ValueError("unexpected or duplicate observation ID")
        observed_ids.add(observation_id)
        mask = entry["masked_id"]
        score_path = judgment_dir / "scores" / f"{mask}.json"
        review = json.loads(score_path.read_text()) if score_path.is_file() else None
        if review is None or blank_template(review, mask):
            label, critical_count = "not_assessable", 0
            unreviewed.append(mask)
        else:
            label = validate_review(review, mask)
            critical_count = len(review["critical_errors"])
        card = result.get("candidate_card") or {}
        cases[result["case_id"]].append({
            "masked_id": mask, "qualitative_label": label,
            "mechanical_pass": result.get("mechanical_pass") is True,
            "contract_pass": card.get("status") == "candidate_for_qualitative_review",
            "critical_error_count": critical_count,
        })
    case_results = {case_id: cluster_gate(items)
                    for case_id, items in sorted(cases.items())}
    complete_panel = (observed_ids == planned and len(case_results) == EXPECTED_CASES
                      and all(item["observation_count"] == REPEATS_PER_CASE
                              for item in case_results.values()))
    adjudication_complete = not unreviewed
    successes = sum(item["gate_pass"] for item in case_results.values())
    lower_event = (one_sided_exact_lower(successes, EXPECTED_CASES, alpha=0.05)
                   if complete_panel and adjudication_complete else None)
    lower_three = (one_sided_exact_lower(successes, EXPECTED_CASES, alpha=0.05 / 3)
                   if complete_panel and adjudication_complete else None)
    return {
        "status": ("incomplete_observation_panel" if not complete_panel
                   else "adjudication_incomplete" if not adjudication_complete
                   else "complete_case_panel"),
        "observations": len(observed_ids), "cases": len(case_results),
        "adjudicated_observations": len(mapping) - len(unreviewed),
        "unreviewed_masked_ids": sorted(unreviewed),
        "case_gate_passes": successes,
        "event_only_one_sided_95_lower_bound": lower_event,
        "three_workflow_bonferroni_one_sided_lower_bound": lower_three,
        "event_only_80_percent_claim_gate":
            complete_panel and adjudication_complete
            and lower_event is not None and lower_event > 0.8,
        "three_workflow_80_percent_claim_gate":
            complete_panel and adjudication_complete
            and lower_three is not None and lower_three > 0.8,
        "case_results": case_results,
        "interpretation_boundary":
            "Codex/LLM judgments diagnostic without independent finance-domain review; event workflow only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--judgment-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("output exists; refusing overwrite")
    result = aggregate(args.results_dir, args.judgment_dir)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({key: value for key, value in result.items()
                      if key != "case_results"}, indent=2))


if __name__ == "__main__":
    main()
