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
DEFAULT_REVIEW_TEMPLATE = Path(__file__).resolve().parent / "stage2_review_template.html"


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


def write_review_page(path: Path, tasks: list[dict[str, Any]], template_path: Path) -> None:
    template = template_path.read_text(encoding="utf-8")
    task_json = json.dumps(tasks, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    marker = "__STAGE2_REVIEW_TASKS__"
    if template.count(marker) != 1:
        raise ValueError(f"review template must contain exactly one {marker} marker")
    path.write_text(template.replace(marker, task_json), encoding="utf-8")


def audit_material(
    evidence: dict[str, Any], suite: dict[str, Any], provenance: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tasks: list[dict[str, Any]] = []
    machine: list[dict[str, Any]] = []
    provenance_by_fact = {row["fact_id"]: row for row in provenance.get("facts", [])}
    fact_by_id = {
        fact["id"]: fact
        for episode in evidence.get("episodes", [])
        for fact in episode.get("facts", [])
    }
    record_by_id: dict[str, dict[str, Any]] = {}
    for case in suite.get("cases", []):
        for record in case.get("records", []):
            existing = record_by_id.setdefault(record["id"], record)
            if existing != record:
                raise ValueError(f"inconsistent duplicate record in suite: {record['id']}")
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
                    "claimed_excerpt": fact.get("excerpt", ""),
                    "input_facts": "",
                    "calculation_spec": "",
                    "record_previews": "",
                    "review_task": (
                        f"在已锁定的一手资料中核验 value={fact.get('value')}、unit={fact.get('unit')}、"
                        f"basis={fact.get('basis')}、period={episode.get('period_label')}，并核对给出的原文摘录。"
                    ),
                    "review_guidance": (
                        "打开 SEC 链接并找到对应原文；先在 independent_result 中独立抄录数值、单位、"
                        "统计口径和报告期间，再选择审阅结论。"
                    ),
                }
            )
            machine.append({"audit_id": audit_id, "expected": json.dumps(fact, sort_keys=True)})
        for category in ("comparisons", "calculations"):
            for index, calculation in enumerate(episode.get(category, []), 1):
                item_id = calculation.get("id") or f"{episode['id']}|{category}|{index}"
                audit_id = "ORACLE|" + item_id
                inputs = {key: value for key, value in calculation.items() if key not in {"expected"}}
                input_ids = [
                    calculation[key]
                    for key in ("numerator_fact", "denominator_fact", "from_fact", "to_fact")
                    if key in calculation
                ]
                input_facts = []
                for fact_id in input_ids:
                    fact = fact_by_id.get(fact_id)
                    if fact is None:
                        raise ValueError(f"calculation references unknown fact: {fact_id}")
                    input_facts.append(
                        {
                            "fact_id": fact_id,
                            "value": fact.get("value"),
                            "unit": fact.get("unit"),
                            "basis": fact.get("basis"),
                        }
                    )
                tasks.append(
                    {
                        "audit_id": audit_id,
                        "audit_type": "oracle_calculation",
                        "item_id": item_id,
                        "source_id": episode["source_id"],
                        "locator": "",
                        "claimed_excerpt": "",
                        "input_facts": json.dumps(input_facts, sort_keys=True),
                        "calculation_spec": json.dumps(inputs, sort_keys=True),
                        "record_previews": "",
                        "review_task": "根据 input_facts 和 calculation_spec 独立重新计算；预期答案有意保持隐藏。",
                        "review_guidance": (
                            "在 independent_result 中写出未舍入的计算过程以及最终舍入结果。"
                            "两名审阅者完成前不得打开 machine-reference.csv。"
                        ),
                    }
                )
                machine.append({"audit_id": audit_id, "expected": str(calculation.get("expected", ""))})
    groups = sorted({tuple(group) for case in suite.get("cases", []) for group in case.get("gold_record_groups", [])})
    for index, group in enumerate(groups, 1):
        audit_id = f"ORACLE-GROUP|{index:03d}"
        previews = []
        for record_id in group:
            record = record_by_id.get(record_id)
            if record is None:
                raise ValueError(f"evidence group references unknown record: {record_id}")
            preview = " ".join(str(record.get("text", "")).split())[:320]
            previews.append(
                {
                    "record_id": record_id,
                    "source_id": record.get("source_id", ""),
                    "locator": record.get("locator", ""),
                    "accepted_at": record.get("accepted_at", ""),
                    "text_preview": preview,
                }
            )
        tasks.append(
            {
                "audit_id": audit_id,
                "audit_type": "evidence_equivalence_group",
                "item_id": audit_id,
                "source_id": "",
                "locator": "",
                "claimed_excerpt": "",
                "input_facts": "",
                "calculation_spec": "",
                "record_previews": json.dumps(previews, sort_keys=True),
                "review_task": "核验以下记录编号能否作为同一必需证据组的有效替代项：" + " | ".join(group),
                "review_guidance": (
                    "比较给出的定位信息和原文预览。在 independent_result 中填写 VALID，或列出任何不等价的"
                    "记录编号；若预览不足以判断，请检查 suite 中的完整文本。"
                ),
            }
        )
        machine.append({"audit_id": audit_id, "expected": json.dumps(group)})
    return tasks, machine


def prepare(
    evidence_path: Path,
    suite_path: Path,
    output_dir: Path,
    provenance_path: Path = DEFAULT_PROVENANCE,
    review_template_path: Path = DEFAULT_REVIEW_TEMPLATE,
) -> dict[str, int]:
    tasks, machine = audit_material(read_json(evidence_path), read_json(suite_path), read_json(provenance_path))
    task_fields = [
        "audit_id", "audit_type", "item_id", "source_id", "locator", "filing_date",
        "accepted_at", "accession", "url", "source_sha256", "claimed_excerpt",
        "input_facts", "calculation_spec", "record_previews", "review_task", "review_guidance",
    ]
    for task in tasks:
        for field in task_fields:
            task.setdefault(field, "")
    write_csv(output_dir / "audit-tasks.csv", tasks, task_fields)
    write_csv(output_dir / "machine-reference.csv", machine, ["audit_id", "expected"])
    reviewer_rows = [
        {**row, "verdict": "", "independent_result": "", "notes": ""}
        for row in tasks
    ]
    reviewer_fields = task_fields + ["verdict", "independent_result", "notes"]
    write_csv(output_dir / "reviewer-a.csv", reviewer_rows, reviewer_fields)
    write_csv(output_dir / "reviewer-b.csv", reviewer_rows, reviewer_fields)
    write_review_page(output_dir / "review.html", tasks, review_template_path)
    (output_dir / "README.md").write_text(
        "# Stage 2 freeze audit\n\n"
        "Two reviewers independently work in `reviewer-a.csv` and `reviewer-b.csv`; each row contains the task context needed for review. `audit-tasks.csv` is the immutable shared task set.\n\n"
        "- Source tasks include the claimed excerpt and SEC URL. Transcribe the independently verified value, unit, basis, and period into `independent_result`.\n"
        "- Calculation tasks include input facts and the operation but hide the expected result. Record the arithmetic and rounded result in `independent_result`.\n"
        "- Evidence-group tasks include record locators and text previews. Record `VALID` or list suspect record IDs in `independent_result`.\n"
        "- Allowed verdicts are `PASS`, `FAIL`, and `NOT_ASSESSABLE`; add a concise note for any non-PASS verdict.\n"
        "- Do not open `machine-reference.csv` until both reviewer files are complete. Any disagreement, failure, or not-assessable item requires documented adjudication before freeze.\n"
        "- 中文审阅界面可直接用浏览器打开 `review.html`。页面含按任务类型展开的字段说明，草稿只保存在浏览器本地，并可导出兼容的 reviewer CSV。\n",
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
            independent_result = str(row.get("independent_result", "")).strip()
            if not audit_id or audit_id in labels:
                raise ValueError(f"missing or duplicate audit_id in {path}: {audit_id}")
            if verdict not in VERDICTS:
                raise ValueError(f"invalid or incomplete verdict for {audit_id} in {path}")
            if not independent_result:
                raise ValueError(f"missing independent_result for {audit_id} in {path}")
            labels[audit_id] = {
                "verdict": verdict,
                "independent_result": independent_result,
                "notes": str(row.get("notes", "")),
            }
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
    prepare_parser.add_argument("--review-template", type=Path, default=DEFAULT_REVIEW_TEMPLATE)
    analyze_parser = commands.add_parser("analyze")
    analyze_parser.add_argument("--tasks", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-a", type=Path, required=True)
    analyze_parser.add_argument("--reviewer-b", type=Path, required=True)
    analyze_parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.evidence, args.suite, args.output_dir, args.provenance, args.review_template)
    else:
        result = analyze(args.tasks, args.reviewer_a, args.reviewer_b, args.output_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
