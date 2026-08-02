#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


EVIDENCE_ID_PATTERN = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}\b")
ACCESSION_PATTERN = re.compile(r"\b\d{10}-\d{2}-\d{6}\b")
DOCUMENT_PATTERN = re.compile(r"\b(?:8-K|EX-99\.1)\b")
NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z0-9-])[-−–]?\d[\d,]*(?:\.\d+)?%?M?(?:pp|bps?)?(?![A-Za-z0-9])",
    re.IGNORECASE,
)
NEGATIVE_BEFORE_PATTERN = re.compile(
    r"(?:declin(?:e|ed)|decreas(?:e|ed)|down|fell|fall|loss|negative)"
    r"(?:\s+(?:first|initially|then|and|by|of|was|were|is|at|usd))*\s*$",
    re.IGNORECASE,
)
COORDINATED_NEGATIVE_BEFORE_PATTERN = re.compile(
    r"(?:declin(?:e|ed)|decreas(?:e|ed)|fell|fall)(?:\s+first)?\s+by\s+"
    r"[-−–]?\d[\d,]*(?:\.\d+)?\s*(?:%|percent|percentage\s+points?|pp|basis\s+points?|bps?)?"
    r"\s+(?:then|and)\s+by\s*$",
    re.IGNORECASE,
)
NEGATIVE_AFTER_PATTERN = re.compile(
    r"^\s*(?:(?:percent|%)|(?:percentage|basis)\s+points?|\-\s*points?)?\s*"
    r"(?:gross[-\s]+margin\s+)?(?:decline|decrease|down|loss)\b",
    re.IGNORECASE,
)
STRUCTURAL_HYPHEN_TRANSLATION = str.maketrans({"‑": "-", "–": "-", "—": "-", "−": "-"})
NUMERIC_CONTEXT_BEFORE_LENGTH = 64
NUMERIC_CONTEXT_AFTER_LENGTH = 48


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_number(value: str, before: str = "", after: str = "") -> str:
    normalized = value.replace("−", "-").replace("–", "-").replace(",", "")
    normalized = re.sub(r"(?:pp|bps?)$", "", normalized, flags=re.IGNORECASE).rstrip("M").rstrip("%")
    negative_context = (
        NEGATIVE_BEFORE_PATTERN.search(before)
        or COORDINATED_NEGATIVE_BEFORE_PATTERN.search(before)
        or NEGATIVE_AFTER_PATTERN.search(after)
    )
    if not normalized.startswith("-") and negative_context:
        return f"-{normalized}"
    return normalized


def numbers(value: str) -> set[str]:
    value = value.translate(STRUCTURAL_HYPHEN_TRANSLATION)
    without_accessions = ACCESSION_PATTERN.sub(" ", value)
    without_documents = DOCUMENT_PATTERN.sub(" ", without_accessions)
    without_ids = EVIDENCE_ID_PATTERN.sub(" ", without_documents)
    return {
        normalized_number(
            match.group(),
            without_ids[max(0, match.start() - NUMERIC_CONTEXT_BEFORE_LENGTH):match.start()],
            without_ids[match.end():match.end() + NUMERIC_CONTEXT_AFTER_LENGTH],
        )
        for match in NUMBER_PATTERN.finditer(without_ids)
        if not is_ordered_list_marker(without_ids, match.start(), match.end())
    }


def is_ordered_list_marker(value: str, start: int, end: int) -> bool:
    line_start = value.rfind("\n", 0, start) + 1
    if value[line_start:start].strip():
        return False
    return value.startswith(". ", end) or value.startswith(") ", end)


def unauthorized_numbers(value: str, authorized: set[str]) -> set[str]:
    value = value.translate(STRUCTURAL_HYPHEN_TRANSLATION)
    without_accessions = ACCESSION_PATTERN.sub(" ", value)
    without_documents = DOCUMENT_PATTERN.sub(" ", without_accessions)
    without_ids = EVIDENCE_ID_PATTERN.sub(" ", without_documents)
    unauthorized = set()
    for match in NUMBER_PATTERN.finditer(without_ids):
        if is_ordered_list_marker(without_ids, match.start(), match.end()):
            continue
        before = without_ids[max(0, match.start() - NUMERIC_CONTEXT_BEFORE_LENGTH):match.start()]
        after = without_ids[match.end():match.end() + NUMERIC_CONTEXT_AFTER_LENGTH]
        normalized = normalized_number(match.group(), before, after)
        if normalized in authorized:
            continue
        if before.rstrip().endswith("(") and after.lstrip().startswith(")"):
            accounting_value = normalized if normalized.startswith("-") else f"-{normalized}"
            if accounting_value in authorized:
                continue
        unauthorized.add(normalized)
    return unauthorized


def evidence_ids(value: str) -> set[str]:
    return set(EVIDENCE_ID_PATTERN.findall(value))


def delegation_evidence(result: str) -> str:
    try:
        payload = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return result
    if isinstance(payload, dict) and isinstance(payload.get("evidence"), str):
        return payload["evidence"]
    return result


def analyze(report_path: Path, suite_path: Path) -> dict[str, Any]:
    report = read_json(report_path)
    suite = read_json(suite_path)
    suite_cases = {case["id"]: case for case in suite.get("cases", [])}
    suite_hash = hashlib.sha256(suite_path.read_bytes()).hexdigest()
    if report.get("source_sha256") != suite_hash:
        raise ValueError(
            "report source_sha256 does not match the supplied suite; analyze the exact suite snapshot used for the run"
        )
    metrics = report.get("metrics", {})
    cases = []
    retained_total = 0
    expected_total = 0
    novel_total = 0
    for case in report.get("cases", []):
        attempt = case["attempts"][0]
        specialist_evidence = []
        delegation_tasks = []
        for event in attempt.get("trace", []):
            if event.get("type") == "tool_result" and event.get("name") == "spawn_subagent":
                specialist_evidence.append(delegation_evidence(event.get("result", "")))
            if event.get("type") == "tool_call" and event.get("name") == "spawn_subagent":
                delegation_tasks.append(event.get("arguments", ""))
        evidence_text = "\n".join(specialist_evidence)
        output = attempt.get("output", "")
        expected_ids = evidence_ids(evidence_text)
        retained_ids = expected_ids & evidence_ids(output)
        missing_ids = expected_ids - retained_ids
        suite_case = suite_cases.get(case["id"], {})
        authorized_numbers = {
            normalized_number(str(value))
            for value in suite_case.get("authorized_numeric_values", [])
        }
        authorized_numbers.update(numbers(evidence_text))
        novel_numbers = unauthorized_numbers(output, authorized_numbers)
        expected_total += len(expected_ids)
        retained_total += len(retained_ids)
        novel_total += len(novel_numbers)
        cases.append(
            {
                "id": case["id"],
                "team_passed": attempt.get("passed", False),
                "expected_evidence_ids": sorted(expected_ids),
                "retained_evidence_ids": sorted(retained_ids),
                "missing_evidence_ids": sorted(missing_ids),
                "evidence_id_retention": len(retained_ids) / len(expected_ids) if expected_ids else 1,
                "unauthorized_numeric_values": sorted(novel_numbers),
                "delegation_mentions_10_k": any("10-K" in task for task in delegation_tasks),
                "failed_graders": [
                    {"type": grader["type"], "message": grader.get("message", "")}
                    for grader in attempt.get("graders", [])
                    if not grader.get("passed", False)
                ],
                "team_latency_ms": next(
                    (
                        baseline.get("latency_ms", 0)
                        for baseline in attempt.get("baselines", [])
                        if baseline.get("mode") == "team"
                    ),
                    0,
                ),
            }
        )
    return {
        "version": 1,
        "report": str(report_path),
        "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
        "suite": str(suite_path),
        "suite_sha256": suite_hash,
        "run": {
            "cases": len(cases),
            "duration_ms": report.get("duration_ms", 0),
            "team_success_rate": metrics.get("multi_agent_team_success_rate", 0),
            "solo_open_book_success_rate": metrics.get("multi_agent_solo_open_book_success_rate", 0),
            "solo_two_pass_success_rate": metrics.get("multi_agent_solo_two_pass_success_rate", 0),
            "oracle_team_success_rate": metrics.get("multi_agent_oracle_team_success_rate", 0),
            "fair_collaboration_gain": metrics.get("multi_agent_fair_collaboration_gain"),
            "delegation_f1": metrics.get("multi_agent_delegation_f1", 0),
            "contribution_utilization": metrics.get("multi_agent_contribution_utilization", 0),
            "contribution_item_coverage": metrics.get("multi_agent_contribution_item_coverage", 0),
            "grounding_accuracy": metrics.get("multi_agent_grounding_accuracy", 0),
            "team_latency_p50_ms": metrics.get("multi_agent_team_latency_p50_ms", 0),
            "team_latency_p95_ms": metrics.get("multi_agent_team_latency_p95_ms", 0),
            "total_tokens": metrics.get("total_tokens", 0),
            "team_tokens": metrics.get("multi_agent_team_total_tokens", 0),
            "total_estimated_cost_usd": metrics.get("multi_agent_total_estimated_cost_usd", 0),
            "team_estimated_cost_usd": metrics.get("multi_agent_team_estimated_cost_usd", 0),
            "evidence_id_retention": retained_total / expected_total if expected_total else 1,
            "unauthorized_numeric_value_count": novel_total,
        },
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze finance team evidence retention and numeric authorization.")
    parser.add_argument("report", type=Path)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = analyze(args.report, args.suite)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
