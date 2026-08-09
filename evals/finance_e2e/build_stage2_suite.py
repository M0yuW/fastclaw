#!/usr/bin/env python3
"""Build the draft Stage 2A suite without modifying the historical Pilot suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from evals.finance_e2e.build_retrieval_suite import (
    DEFAULT_EVIDENCE,
    DEFAULT_LOCK,
    DEFAULT_SOURCES,
    ROOT,
    build_suite,
    read_json,
    write_json,
)


DEFAULT_OUTPUT = ROOT / "evals" / "finance-retrieval-stage2a-v2.json"
DEFAULT_ACCEPTANCE_LOCK = ROOT / "evals" / "finance_e2e" / "acceptance-time-lock.json"
PRIMARY_MODES = ["solo_staged", "team_shared_retrieval", "team_raw_context"]
DIAGNOSTIC_MODES = ["solo_monolithic", "oracle_evidence"]
ABLATION_MODE = "team_shared_retrieval_all_pro"


def case_metadata(case_id: str) -> tuple[str, str, str]:
    parts = case_id.split("-")
    if len(parts) != 4 or parts[0] != "FRET" or parts[2] not in {"POINT", "LONG"}:
        raise ValueError(f"unexpected retrieval case ID: {case_id}")
    company = parts[1]
    task_family = "point_in_time" if parts[2] == "POINT" else "longitudinal"
    return company, task_family, f"{company}|{task_family}"


def build_stage2_suite(
    evidence: Path, sources: Path, lock: Path, acceptance_lock: Path = DEFAULT_ACCEPTANCE_LOCK
) -> dict[str, Any]:
    suite = build_suite(evidence, sources, lock)
    accepted_by_accession = {
        row["accession"]: row for row in read_json(acceptance_lock)["entries"]
    }
    for case in suite["cases"]:
        for record in case["records"]:
            accepted = accepted_by_accession.get(record["accession"])
            if accepted is None:
                raise ValueError(f"missing acceptance metadata: {record['accession']}")
            if accepted["filing_date"] != record["filed_at"]:
                raise ValueError(f"acceptance metadata filing-date mismatch: {record['accession']}")
            record["accepted_at"] = accepted["accepted_at"]
    suite.update(
        {
            "study": "finance-sec-retrieval-stage2a-v1",
            "status": "draft",
            "name": "finance-sec-retrieval-context-v2",
            "description": (
                "Draft Stage 2A paired retrieval/context study. Formal execution is prohibited "
                "until the protocol and suite status are frozen."
            ),
            "primary_modes": PRIMARY_MODES,
            "diagnostic_modes": DIAGNOSTIC_MODES,
            "ablation_modes": [ABLATION_MODE],
            "randomization_seed": 20260802,
            "prompt_version": "finance-retrieval-stage2a-prompt-v1",
            "grader_version": "finance-retrieval-stage2a-grader-v1",
            "pricing_date": "2026-08-01",
            "model_allocation": {
                "coordinator": "deepseek/deepseek-v4-pro",
                "solo_staged": "deepseek/deepseek-v4-pro",
                "retriever": "deepseek/deepseek-v4-flash",
                "specialists": "deepseek/deepseek-v4-flash",
                "capacity_matched_team": "deepseek/deepseek-v4-pro",
            },
            "execution_controls": {
                "thinking_mode": "off",
                "temperature": 0.1,
                "max_output_tokens": {
                    "coordinator": 8192,
                    "solo": 8192,
                    "retriever": 8192,
                    "specialists": 8192,
                },
                "provider_concurrency": "one case block; Team specialists parallel within block",
            },
        }
    )
    suite["defaults"]["repetitions"] = 3
    suite["defaults"]["min_final_evidence_recall"] = 0.90
    suite["defaults"]["capacity_matched_model"] = "deepseek/deepseek-v4-pro"
    suite["modes"] = PRIMARY_MODES + DIAGNOSTIC_MODES + [ABLATION_MODE]

    ablation_cases: list[str] = []
    for case in suite["cases"]:
        company, task_family, cluster_id = case_metadata(case["id"])
        case["company"] = company
        case["task_family"] = task_family
        case["cluster_id"] = cluster_id
        if task_family == "point_in_time":
            gold_ids = set(case["gold_record_ids"])
            target_times = [record["accepted_at"] for record in case["records"] if record["id"] in gold_ids]
            if not target_times:
                raise ValueError(f"point-in-time case has no dated gold records: {case['id']}")
            as_of_timestamp = max(target_times)
            excluded = sorted({record["source_id"] for record in case["records"] if record["accepted_at"] > as_of_timestamp})
            case["records"] = [record for record in case["records"] if record["accepted_at"] <= as_of_timestamp]
            case["as_of_timestamp"] = as_of_timestamp
            case["accepted_at_verified"] = True
            case["temporal_verification_note"] = (
                "Verified against the locked SEC submissions API acceptance timestamp; "
                "later-accepted candidate corpus sources are excluded."
            )
            case["excluded_future_source_ids"] = excluded
        if (task_family == "longitudinal" and case["corpus_load"] == "medium") or (
            task_family == "point_in_time" and case["corpus_load"] == "large"
        ):
            ablation_cases.append(case["id"])
    suite["ablation_case_ids"] = sorted(ablation_cases)
    if len(suite["cases"]) != 24 or len(set(case["cluster_id"] for case in suite["cases"])) != 8:
        raise ValueError("Stage 2A must contain 24 configurations and 8 company-task clusters")
    if len(ablation_cases) != 8:
        raise ValueError("Stage 2A all-Pro ablation must contain 8 prespecified configurations")
    suite["formal_freeze_blockers"] = [
        "Complete two independent human reviews of all 98 source/oracle freeze-audit items and adjudicate every non-PASS item."
    ]
    return suite


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    parser.add_argument("--acceptance-lock", type=Path, default=DEFAULT_ACCEPTANCE_LOCK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    suite = build_stage2_suite(args.evidence, args.sources, args.lock, args.acceptance_lock)
    if args.check:
        if not args.output.exists() or read_json(args.output) != suite:
            raise RuntimeError(f"generated Stage 2 artifact is stale: {args.output}")
        print("Stage 2A suite is valid and current")
        return 0
    write_json(args.output, suite)
    print(json.dumps({"output": str(args.output), "status": suite["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
