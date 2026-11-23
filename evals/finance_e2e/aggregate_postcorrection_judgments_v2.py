#!/usr/bin/env python3
"""Validate masked claim reviews, then aggregate the frozen v2 event holdout.

No answer is scored by this code. Reviewer-written score files are checked
against the predeclared rubric; mechanical results are joined only after the
qualitative score files exist. Raw observations are never modified.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

from run_thesis_event_panel import sha256


DIMENSIONS = ("F", "I", "R", "S", "U")
VERDICTS = {"supported", "bounded_hypothesis", "unsupported", "contradicted",
            "unassessable"}
LOCATIONS = {"final_answer", "persisted_review"}
EXPECTED_CASES = 20
REPEATS_PER_CASE = 5
BONFERRONI_ALPHA = 0.05 / 3


def verify_frozen_results(results_dir: Path) -> None:
    """Require the runner's complete, matching hash list before adjudication."""
    hash_path = results_dir / "RESULT-SHA256.txt"
    if not hash_path.is_file():
        raise ValueError("frozen result hash list is missing")
    expected = {Path("manifest.json")}
    expected.update(path.relative_to(results_dir)
                    for path in results_dir.glob("*/result.json"))
    expected.update(path.relative_to(results_dir)
                    for path in results_dir.glob("*/finance-tools.db"))
    listed = {}
    for line in hash_path.read_text().splitlines():
        pieces = line.split("  ", 1)
        if len(pieces) != 2 or len(pieces[0]) != 64:
            raise ValueError("malformed frozen result hash list")
        relative = Path(pieces[1])
        if relative.is_absolute() or ".." in relative.parts or relative in listed:
            raise ValueError("unsafe or duplicate frozen result path")
        listed[relative] = pieces[0]
    if set(listed) != expected:
        raise ValueError("frozen result hash list is incomplete or has extras")
    for relative, digest in listed.items():
        path = results_dir / relative
        if not path.is_file() or sha256(path) != digest:
            raise ValueError(f"frozen result hash mismatch: {relative}")


def validate_review(review: dict, masked_id: str) -> str:
    if review.get("masked_id") != masked_id:
        raise ValueError(f"score ID mismatch: {masked_id}")
    if not str(review.get("reviewer", "")).strip():
        raise ValueError(f"missing reviewer identity: {masked_id}")
    scores = review.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(DIMENSIONS):
        raise ValueError(f"five F/I/R/S/U scores required: {masked_id}")
    if any(value not in (0, 1, 2, None) for value in scores.values()):
        raise ValueError(f"invalid F/I/R/S/U value: {masked_id}")
    claims = review.get("claim_adjudications")
    critical = review.get("critical_errors")
    if not isinstance(claims, list) or not isinstance(critical, list):
        raise ValueError(f"claim and critical-error lists required: {masked_id}")
    for index, claim in enumerate(claims):
        if claim.get("location") not in LOCATIONS or claim.get("verdict") not in VERDICTS:
            raise ValueError(f"invalid claim location/verdict: {masked_id} #{index}")
        if not str(claim.get("span", "")).strip():
            raise ValueError(f"exact claim span required: {masked_id} #{index}")
        if not isinstance(claim.get("evidence_refs"), list):
            raise ValueError(f"evidence references required: {masked_id} #{index}")
        if claim["verdict"] != "unassessable" and not claim["evidence_refs"]:
            raise ValueError(f"supported/contested claim lacks evidence: {masked_id} #{index}")
    for error in critical:
        index = error.get("claim_index")
        if not isinstance(index, int) or not 0 <= index < len(claims):
            raise ValueError(f"critical error lacks claim pointer: {masked_id}")
        if not str(error.get("code", "")).strip() or not error.get("evidence_refs"):
            raise ValueError(f"critical error lacks code/evidence: {masked_id}")
    coverage = review.get("coverage")
    if not isinstance(coverage, dict) or set(coverage) != LOCATIONS or any(
            value not in (True, False) for value in coverage.values()):
        raise ValueError(f"final and persisted-review coverage required: {masked_id}")
    if critical or any(value == 0 for value in scores.values()):
        return "problematic"
    if any(value is None for value in scores.values()) or not all(coverage.values()):
        if not str(review.get("notes", "")).strip():
            raise ValueError(f"not-assessable review needs a reason: {masked_id}")
        return "not_assessable"
    if not claims:
        raise ValueError(f"scored answer has no material claim audit: {masked_id}")
    if all(value == 2 for value in scores.values()) and review.get("assessable_implication") is True:
        return "high"
    if any(value == 1 for value in scores.values()):
        return "adequate"
    raise ValueError(f"complete 2/2 score lacks assessable implication: {masked_id}")


def blank_template(review: dict, masked_id: str) -> bool:
    return (review.get("masked_id") == masked_id
            and not review.get("reviewer")
            and review.get("coverage") == {"final_answer": False,
                                            "persisted_review": False}
            and review.get("scores") == {name: None for name in DIMENSIONS}
            and review.get("claim_adjudications") == []
            and review.get("critical_errors") == [])


def binomial_upper_tail(n: int, k: int, probability: float) -> float:
    return sum(math.comb(n, i) * probability ** i * (1 - probability) ** (n - i)
               for i in range(k, n + 1))


def one_sided_exact_lower(successes: int, total: int,
                          alpha: float = BONFERRONI_ALPHA) -> float:
    if total <= 0 or not 0 <= successes <= total or not 0 < alpha < 1:
        raise ValueError("invalid binomial inputs")
    if successes == 0:
        return 0.0
    low, high = 0.0, 1.0
    for _ in range(80):
        middle = (low + high) / 2
        if binomial_upper_tail(total, successes, middle) < alpha:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def case_gate(observations: list[dict]) -> dict:
    counts = Counter(item["qualitative_label"] for item in observations)
    complete = len(observations) == REPEATS_PER_CASE
    passed = (complete and all(item["mechanical_pass"] for item in observations)
              and all(item["critical_error_count"] == 0 for item in observations)
              and counts["high"] >= 4 and counts["adequate"] <= 1
              and counts["problematic"] == counts["not_assessable"] == 0)
    return {"observation_count": len(observations),
            "labels": dict(counts), "gate_pass": passed}


def aggregate(results_dir: Path, judgment_dir: Path) -> dict:
    verify_frozen_results(results_dir)
    mapping_path = judgment_dir / "PRIVATE-MAPPING.json"
    mapping = json.loads(mapping_path.read_text())
    if not isinstance(mapping, list) or len({m["masked_id"] for m in mapping}) != len(mapping):
        raise ValueError("invalid or duplicate masked mapping")
    all_results = sorted(results_dir.glob("*/result.json"))
    if len(all_results) != len(mapping):
        raise ValueError("not every result has a masked mapping")
    result_paths = {path.resolve() for path in all_results}
    cases: dict[str, list[dict]] = defaultdict(list)
    unreviewed = []
    for entry in mapping:
        raw = Path(entry["raw_result_path"])
        if raw.resolve() not in result_paths:
            raise ValueError(f"mapping points outside frozen result set: {raw}")
        if sha256(raw) != entry["raw_result_sha256"]:
            raise ValueError(f"raw result hash mismatch: {raw}")
        result = json.loads(raw.read_text())
        if result.get("observation_id") != entry["observation_id"]:
            raise ValueError(f"observation ID mismatch: {raw}")
        mask = entry["masked_id"]
        score_path = judgment_dir / "scores" / f"{mask}.json"
        review = json.loads(score_path.read_text()) if score_path.is_file() else None
        if review is None or blank_template(review, mask):
            label, critical_count = "not_assessable", 0
            unreviewed.append(mask)
        else:
            label = validate_review(review, mask)
            critical_count = len(review["critical_errors"])
        cases[result["case_id"]].append({
            "masked_id": mask, "qualitative_label": label,
            "mechanical_pass": result.get("status") == "mechanical_pass",
            "critical_error_count": critical_count,
        })
    case_results = {}
    for case_id, observations in sorted(cases.items()):
        case_results[case_id] = case_gate(observations)
    complete_panel = (len(mapping) == EXPECTED_CASES * REPEATS_PER_CASE
                      and len(case_results) == EXPECTED_CASES
                      and all(item["observation_count"] == REPEATS_PER_CASE
                              for item in case_results.values()))
    successes = sum(item["gate_pass"] for item in case_results.values())
    adjudication_complete = not unreviewed
    lower = (one_sided_exact_lower(successes, EXPECTED_CASES)
             if complete_panel and adjudication_complete else None)
    status = ("incomplete_observation_panel" if not complete_panel
              else "adjudication_incomplete" if not adjudication_complete
              else "complete_case_panel")
    return {"status": status,
            "observations": len(mapping), "cases": len(case_results),
            "adjudicated_observations": len(mapping) - len(unreviewed),
            "unreviewed_masked_ids": sorted(unreviewed),
            "case_gate_passes": successes,
            "bonferroni_one_sided_95_lower_bound": lower,
            "predeclared_all_20_gate_met": complete_panel and adjudication_complete
                and successes == EXPECTED_CASES
                and lower is not None and lower > 0.8,
            "case_results": case_results,
            "interpretation_boundary": "Codex/LLM diagnostic without independent finance-expert rating; event workflow only"}


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
