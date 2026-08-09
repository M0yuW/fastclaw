#!/usr/bin/env python3
"""Prepare and analyze independent human source/oracle freeze audits for Stage 2."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


VERDICTS = {"PASS", "FAIL", "NOT_ASSESSABLE"}
DEFAULT_PROVENANCE = Path(__file__).resolve().parent / "gold-fact-provenance.json"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def audit_material(
    evidence: dict[str, Any], suite: dict[str, Any], provenance: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    machine: list[dict[str, Any]] = []
    provenance_by_fact = {row["fact_id"]: row for row in provenance.get("facts", [])}
    for episode in evidence.get("episodes", []):
        for fact in episode.get("facts", []):
            audit_id = "SOURCE|" + fact["id"]
            provenance_row = provenance_by_fact.get(fact["id"])
            if provenance_row is None:
                raise ValueError(f"fact is missing from provenance: {fact['id']}")
            tasks.append(
                {
                    "audit_id": audit_id,
                    "audit_type": "source",
                    "item_id": fact["id"],
                    "source_id": episode["source_id"],
                    "locator": fact.get("locator", ""),
                    "filing_date": provenance_row["filing_date"],
                    "accepted_at": provenance_row["accepted_at"],
                    "accession": provenance_row["accession"],
                    "url": provenance_row["url"],
                    "source_sha256": provenance_row["source_sha256"],
                    "review_task": (
                        f"Verify value={fact.get('value')} unit={fact.get('unit')} basis={fact.get('basis')} "
                        f"period={episode.get('period_label')} and the claimed excerpt in the locked primary source."
                    ),
                }
            )
            machine.append({"audit_id": audit_id, "expected": json.dumps(fact, sort_keys=True)})
        for category in ("comparisons", "calculations"):
            for index, calculation in enumerate(episode.get(category, []), 1):
                item_id = calculation.get("id") or f"{episode['id']}|{category}|{index}"
                audit_id = "ORACLE|" + item_id
                inputs = {key: value for key, value in calculation.items() if key not in {"expected"}}
                tasks.append(
                    {
                        "audit_id": audit_id,
                        "audit_type": "oracle_calculation",
                        "item_id": item_id,
                        "source_id": episode["source_id"],
                        "locator": "",
                        "review_task": "Independently recompute from the referenced facts: " + json.dumps(inputs, sort_keys=True),
                    }
                )
                machine.append({"audit_id": audit_id, "expected": str(calculation.get("expected", ""))})
    groups = sorted({tuple(group) for case in suite.get("cases", []) for group in case.get("gold_record_groups", [])})
    for index, group in enumerate(groups, 1):
        audit_id = f"ORACLE-GROUP|{index:03d}"
        tasks.append(
            {
                "audit_id": audit_id,
                "audit_type": "evidence_equivalence_group",
                "item_id": audit_id,
                "source_id": "",
                "locator": "",
                "review_task": "Verify that these record IDs are valid alternatives for one required evidence group: " + " | ".join(group),
            }
        )
        machine.append({"audit_id": audit_id, "expected": json.dumps(group)})
    return tasks, machine


def prepare(
    evidence_path: Path, suite_path: Path, output_dir: Path, provenance_path: Path = DEFAULT_PROVENANCE
) -> dict[str, int]:
    tasks, machine = audit_material(read_json(evidence_path), read_json(suite_path), read_json(provenance_path))
    task_fields = [
        "audit_id", "audit_type", "item_id", "source_id", "locator", "filing_date",
        "accepted_at", "accession", "url", "source_sha256", "review_task",
    ]
    for task in tasks:
        for field in task_fields:
            task.setdefault(field, "")
    write_csv(output_dir / "audit-tasks.csv", tasks, task_fields)
    write_csv(output_dir / "machine-reference.csv", machine, ["audit_id", "expected"])
    reviewer_rows = [{"audit_id": row["audit_id"], "verdict": "", "notes": ""} for row in tasks]
    write_csv(output_dir / "reviewer-a.csv", reviewer_rows, ["audit_id", "verdict", "notes"])
    write_csv(output_dir / "reviewer-b.csv", reviewer_rows, ["audit_id", "verdict", "notes"])
    (output_dir / "README.md").write_text(
        "# Stage 2 freeze audit\n\n"
        "Two reviewers independently inspect `audit-tasks.csv` and the locked primary sources. "
        "They must not open `machine-reference.csv` until both reviewer files are complete. "
        "Allowed verdicts are PASS, FAIL, and NOT_ASSESSABLE. Any disagreement, failure, or "
        "not-assessable item requires documented adjudication before freeze.\n",
        encoding="utf-8",
    )
    return {
        "tasks": len(tasks),
        "source": sum(row["audit_type"] == "source" for row in tasks),
        "oracle_calculation": sum(row["audit_type"] == "oracle_calculation" for row in tasks),
        "evidence_groups": sum(row["audit_type"] == "evidence_equivalence_group" for row in tasks),
    }


def reviewer_labels(path: Path) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            audit_id = str(row.get("audit_id", "")).strip()
            verdict = str(row.get("verdict", "")).strip().upper()
            if not audit_id or audit_id in labels:
                raise ValueError(f"missing or duplicate audit_id in {path}: {audit_id}")
            if verdict not in VERDICTS:
                raise ValueError(f"invalid or incomplete verdict for {audit_id} in {path}")
            labels[audit_id] = {"verdict": verdict, "notes": str(row.get("notes", ""))}
    return labels


def analyze(tasks_path: Path, reviewer_a_path: Path, reviewer_b_path: Path, output_dir: Path) -> dict[str, Any]:
    with tasks_path.open(newline="", encoding="utf-8") as handle:
        tasks = list(csv.DictReader(handle))
    task_ids = [row["audit_id"] for row in tasks]
    reviewer_a = reviewer_labels(reviewer_a_path)
    reviewer_b = reviewer_labels(reviewer_b_path)
    if set(reviewer_a) != set(task_ids) or set(reviewer_b) != set(task_ids):
        raise ValueError("reviewer files do not cover exactly the frozen audit task set")
    disagreements = []
    all_pass = True
    agreements = 0
    for audit_id in task_ids:
        left = reviewer_a[audit_id]["verdict"]
        right = reviewer_b[audit_id]["verdict"]
        if left == right:
            agreements += 1
        if left != "PASS" or right != "PASS":
            all_pass = False
            disagreements.append(
                {
                    "audit_id": audit_id,
                    "reviewer_a": left,
                    "reviewer_b": right,
                    "adjudicated_verdict": "",
                    "adjudicator_notes": "",
                }
            )
    write_csv(
        output_dir / "adjudication.csv",
        disagreements,
        ["audit_id", "reviewer_a", "reviewer_b", "adjudicated_verdict", "adjudicator_notes"],
    )
    result = {
        "tasks": len(task_ids),
        "raw_agreement": agreements / len(task_ids) if task_ids else 0,
        "items_requiring_adjudication": len(disagreements),
        "freeze_audit_passed": all_pass,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "audit-summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--evidence", type=Path, required=True)
    prepare_parser.add_argument("--suite", type=Path, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, required=True)
    prepare_parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--tasks", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-a", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-b", type=Path, required=True)
    analyze_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.evidence, args.suite, args.output_dir, args.provenance)
    else:
        result = analyze(args.tasks, args.reviewer_a, args.reviewer_b, args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
