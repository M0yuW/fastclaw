#!/usr/bin/env python3
"""Prepare and analyze blinded human validation of the retained r5 grader."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import yaml


LABELS = {
    "milestone": {"satisfied", "not_satisfied", "not_assessable"},
    "grounding": {"violation", "no_violation", "not_assessable"},
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_suite(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("suite must contain a cases list")
    return payload


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def team_attempt(report_case: dict[str, Any]) -> dict[str, Any]:
    attempts = report_case.get("attempts", [])
    if len(attempts) != 1:
        raise ValueError(f"{report_case.get('id')}: expected exactly one retained r5 attempt")
    return attempts[0]


def prepare_r5(report_path: Path, suite_path: Path, output_dir: Path) -> dict[str, int]:
    report = read_json(report_path)
    suite = read_suite(suite_path)
    report_cases = {case["id"]: case for case in report.get("cases", [])}
    suite_cases = {case["id"]: case for case in suite["cases"]}
    if set(report_cases) != set(suite_cases):
        raise ValueError("report and suite case IDs differ")

    tasks: list[dict[str, Any]] = []
    machine_labels: dict[str, dict[str, str]] = {}
    for case_id, suite_case in suite_cases.items():
        attempt = team_attempt(report_cases[case_id])
        output = attempt.get("output", "")
        evidence = [
            {
                "agent_id": agent.get("id", ""),
                "role": agent.get("role", ""),
                "response": agent.get("response", ""),
            }
            for agent in suite_case.get("agents", [])
        ]
        milestone_results = [
            grader
            for grader in attempt.get("graders", [])
            if grader.get("type") == "ma_milestone"
        ]
        milestones = suite_case.get("milestones", [])
        if len(milestone_results) != len(milestones):
            raise ValueError(f"{case_id}: milestone grader count does not match suite")
        for milestone, result in zip(milestones, milestone_results):
            item_id = f"{case_id}::milestone::{milestone['id']}"
            tasks.append(
                {
                    "item_id": item_id,
                    "case_id": case_id,
                    "item_type": "milestone",
                    "criterion": milestone.get("values", []),
                    "evidence": evidence,
                    "model_output": output,
                    "instruction": (
                        "Label satisfied only when the output fulfills every criterion group "
                        "without reversing or conditionally disclaiming the required meaning."
                    ),
                }
            )
            machine_labels[item_id] = {
                "item_type": "milestone",
                "label": "satisfied" if result.get("passed") else "not_satisfied",
            }

        forbidden = suite_case.get("forbidden_output_values", [])
        metrics = attempt.get("multi_agent", {})
        if metrics.get("grounding_assertions") != len(forbidden):
            raise ValueError(f"{case_id}: grounding assertion count does not match suite")
        if metrics.get("grounding_violations") != 0:
            raise ValueError(
                f"{case_id}: retained report has aggregate grounding violations; "
                "per-assertion machine labels are unavailable"
            )
        for index, criterion in enumerate(forbidden, start=1):
            item_id = f"{case_id}::grounding::{index:02d}"
            tasks.append(
                {
                    "item_id": item_id,
                    "case_id": case_id,
                    "item_type": "grounding",
                    "criterion": criterion,
                    "evidence": evidence,
                    "model_output": output,
                    "instruction": (
                        "Label violation only when the output affirmatively makes the forbidden "
                        "claim. A denial, hedge, quotation, or rejected candidate is not "
                        "automatically a violation; use not_assessable when scope is ambiguous."
                    ),
                }
            )
            machine_labels[item_id] = {"item_type": "grounding", "label": "no_violation"}

    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "tasks.jsonl", tasks)
    write_json(output_dir / "machine-labels.json", machine_labels)
    for reviewer in ("reviewer-a.csv", "reviewer-b.csv"):
        with (output_dir / reviewer).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["item_id", "item_type", "label", "notes"])
            writer.writeheader()
            for task in tasks:
                writer.writerow(
                    {
                        "item_id": task["item_id"],
                        "item_type": task["item_type"],
                        "label": "",
                        "notes": "",
                    }
                )
    write_json(
        output_dir / "README.json",
        {
            "status": "annotation-template",
            "blinding": "Do not provide machine-labels.json to reviewers before both sheets are locked.",
            "labels": {key: sorted(value) for key, value in LABELS.items()},
            "counts": Counter(task["item_type"] for task in tasks),
            "adjudication": "Resolve disagreements only after independent sheets are complete.",
        },
    )
    return dict(Counter(task["item_type"] for task in tasks))


def read_annotations(path: Path, expected: dict[str, str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            item_id = row.get("item_id", "")
            item_type = row.get("item_type", "")
            label = row.get("label", "").strip()
            if item_id not in expected:
                raise ValueError(f"{path}: unexpected item ID {item_id!r}")
            if item_type != expected[item_id]:
                raise ValueError(f"{path}: wrong item type for {item_id}")
            if label not in LABELS[item_type]:
                raise ValueError(f"{path}: invalid or blank label for {item_id}: {label!r}")
            if item_id in labels:
                raise ValueError(f"{path}: duplicate item ID {item_id}")
            labels[item_id] = label
    missing = set(expected) - set(labels)
    if missing:
        raise ValueError(f"{path}: missing {len(missing)} annotations")
    return labels


def cohen_kappa(left: list[str], right: list[str]) -> float | None:
    if len(left) != len(right) or not left:
        return None
    labels = sorted(set(left) | set(right))
    observed = sum(a == b for a, b in zip(left, right)) / len(left)
    left_counts = Counter(left)
    right_counts = Counter(right)
    expected = sum(left_counts[label] * right_counts[label] for label in labels) / len(left) ** 2
    if expected == 1:
        return 1.0 if observed == 1 else None
    return (observed - expected) / (1 - expected)


def confusion(machine: list[str], human: list[str]) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for expected, observed in zip(machine, human):
        matrix.setdefault(expected, {})[observed] = matrix.setdefault(expected, {}).get(observed, 0) + 1
    return matrix


def analyze(
    tasks_path: Path,
    machine_path: Path,
    reviewer_a_path: Path,
    reviewer_b_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line]
    expected = {task["item_id"]: task["item_type"] for task in tasks}
    machine_payload = read_json(machine_path)
    if set(machine_payload) != set(expected):
        raise ValueError("machine-label IDs do not match tasks")
    reviewer_a = read_annotations(reviewer_a_path, expected)
    reviewer_b = read_annotations(reviewer_b_path, expected)

    result: dict[str, Any] = {"items": len(tasks), "by_type": {}}
    disagreements: list[dict[str, str]] = []
    for item_type in sorted(LABELS):
        item_ids = [task["item_id"] for task in tasks if task["item_type"] == item_type]
        labels_a = [reviewer_a[item_id] for item_id in item_ids]
        labels_b = [reviewer_b[item_id] for item_id in item_ids]
        machine = [machine_payload[item_id]["label"] for item_id in item_ids]
        result["by_type"][item_type] = {
            "items": len(item_ids),
            "raw_agreement": sum(a == b for a, b in zip(labels_a, labels_b)) / len(item_ids),
            "cohen_kappa": cohen_kappa(labels_a, labels_b),
            "reviewer_a_vs_machine": confusion(machine, labels_a),
            "reviewer_b_vs_machine": confusion(machine, labels_b),
            "reviewer_a_not_assessable": labels_a.count("not_assessable"),
            "reviewer_b_not_assessable": labels_b.count("not_assessable"),
        }
        for item_id, label_a, label_b in zip(item_ids, labels_a, labels_b):
            if label_a != label_b:
                disagreements.append(
                    {
                        "item_id": item_id,
                        "item_type": item_type,
                        "reviewer_a": label_a,
                        "reviewer_b": label_b,
                        "adjudicated_label": "",
                        "resolution_notes": "",
                    }
                )
    return result, disagreements


def write_disagreements(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "item_id",
        "item_type",
        "reviewer_a",
        "reviewer_b",
        "adjudicated_label",
        "resolution_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare-r5")
    prepare.add_argument("--report", type=Path, required=True)
    prepare.add_argument("--suite", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("--tasks", type=Path, required=True)
    analyze_parser.add_argument("--machine-labels", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-a", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-b", type=Path, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    analyze_parser.add_argument("--disagreements", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "prepare-r5":
        counts = prepare_r5(args.report, args.suite, args.output_dir)
        print(json.dumps({"status": "prepared", "counts": counts}, sort_keys=True))
        return 0
    result, disagreements = analyze(
        args.tasks,
        args.machine_labels,
        args.reviewer_a,
        args.reviewer_b,
    )
    write_json(args.output, result)
    write_disagreements(args.disagreements, disagreements)
    print(json.dumps({"status": "analyzed", "disagreements": len(disagreements)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
