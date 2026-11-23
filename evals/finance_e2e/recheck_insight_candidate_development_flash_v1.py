#!/usr/bin/env python3
"""Read-only recheck of sealed typed-candidate development observations."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import run_insight_candidate_development_flash_v1 as run
import validate_structured_financial_claims_v1 as arithmetic
from run_thesis_event_panel import sha256
from verify_insight_candidate_v1 import verify_candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    paths = sorted(args.input_dir.glob("*/result.json"))
    if len(paths) != 8:
        raise ValueError("expected eight sealed development observations")
    rows = []
    issues = Counter()
    for path in paths:
        original = json.loads(path.read_text())
        final = original["turns"][-1]["response"]["choices"][0]["message"].get("content")
        try:
            candidate = json.loads(final) if final else None
        except (json.JSONDecodeError, TypeError):
            candidate = None
        symbol = original["observation_id"].split("-", 1)[0]
        verdict = verify_candidate(run.selected_facts(symbol), candidate, original["state"])
        issues.update(verdict["issues"])
        checked = verdict.get("structured_claim_check", {}).get("items", [])
        claims = candidate.get("claims", []) if isinstance(candidate, dict) else []
        failures = [
            {"claim_index": index, "claim": claim, "verdict": item}
            for index, (claim, item) in enumerate(zip(claims, checked))
            if item.get("status") != "verified"
        ]
        rows.append({
            "observation_id": original["observation_id"],
            "original_status": original["status"],
            "rechecked_status": verdict["status"],
            "rechecked_issues": verdict["issues"],
            "invalid_structured_claims": failures,
            "result_sha256": sha256(path),
        })
    summary = {
        "purpose": "offline verifier-bug diagnosis; no model requests or observation reruns",
        "source_result_dir": str(args.input_dir.resolve()),
        "observations": len(rows),
        "original_candidate_count": sum(row["original_status"] == "candidate_for_qualitative_review"
                                        for row in rows),
        "rechecked_candidate_count": sum(row["rechecked_status"] == "candidate_for_qualitative_review"
                                         for row in rows),
        "issue_counts": dict(sorted(issues.items())),
        "quality_pass": None,
        "rows": rows,
        "checker_sha256": sha256(Path(__file__).with_name("verify_insight_candidate_v1.py")),
        "arithmetic_checker_sha256": sha256(Path(arithmetic.__file__)),
        "rechecker_sha256": sha256(Path(__file__)),
    }
    args.output_dir.mkdir(parents=True)
    output = args.output_dir / "RECHECK.json"
    output.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text(
        f"{sha256(output)}  {output.name}\n")
    print(json.dumps({key: value for key, value in summary.items() if key != "rows"},
                     indent=2))


if __name__ == "__main__":
    main()
