#!/usr/bin/env python3
"""Create secret-free Stage 2 manifests and analyze retained confirmatory JSON."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import random
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PRIMARY_MODES = ("solo_staged", "team_shared_retrieval", "team_raw_context")
FORBIDDEN_FORMAL_LABELS = ("calibration", "pilot", "diagnostic", "superseded")
SECRET_KEY_PARTS = ("api_key", "apikey", "authorization", "access_token", "secret")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_output(command: list[str], cwd: Path) -> str:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def assert_secret_free(value: Any, location: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in SECRET_KEY_PARTS):
                raise ValueError(f"secret-bearing key is prohibited in {location}: {key}")
            assert_secret_free(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_secret_free(child, f"{location}[{index}]")


def file_record(path: Path) -> dict[str, Any]:
    return {"name": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def create_manifest(
    suite_path: Path,
    source_lock_path: Path,
    protocol_path: Path,
    prompt_grader_path: Path,
    agent_source_path: Path,
    executable_path: Path,
    report_path: Path | None,
    status: str,
) -> dict[str, Any]:
    suite = read_json(suite_path)
    report = read_json(report_path) if report_path is not None else None
    if status == "confirmatory" and suite.get("status") != "frozen":
        raise ValueError("confirmatory manifest requires a frozen suite")
    if status == "confirmatory" and report is not None and report.get("status") != "frozen":
        raise ValueError("confirmatory manifest requires a frozen report")
    if report is not None and report.get("study") != suite.get("study"):
        raise ValueError("report study does not match suite study")
    suite_hash = sha256_file(suite_path)
    if report is not None and report.get("source_sha256") != suite_hash:
        raise ValueError("report suite hash does not match retained suite")
    if report is not None and report.get("source_lock_sha256") != suite.get("source_lock_sha256"):
        raise ValueError("report source-lock hash does not match suite")
    if report is not None and report.get("randomization_seed") != suite.get("randomization_seed"):
        raise ValueError("report randomization seed does not match suite")
    if sha256_file(source_lock_path) != suite.get("source_lock_sha256"):
        raise ValueError("retained source-lock file does not match suite")
    if report is not None:
        validate_model_allocation(report, suite)

    repo_root = suite_path.resolve().parents[1]
    manifest = {
        "schema_version": 1,
        "study": suite.get("study"),
        "artifact_status": status,
        "protocol_status": suite.get("status"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "randomization_seed": suite.get("randomization_seed"),
        "design": {
            "primary_modes": suite.get("primary_modes", list(PRIMARY_MODES)),
            "configurations": len(suite.get("cases", [])),
            "repetitions": suite.get("defaults", {}).get("repetitions"),
            "expected_pair_blocks": len(suite.get("cases", [])) * int(suite.get("defaults", {}).get("repetitions", 0)),
            "expected_primary_observations": len(suite.get("cases", []))
            * int(suite.get("defaults", {}).get("repetitions", 0))
            * len(suite.get("primary_modes", PRIMARY_MODES)),
        },
        "versions": {
            "prompt": suite.get("prompt_version"),
            "grader": suite.get("grader_version"),
            "pricing_date": suite.get("pricing_date"),
        },
        "runtime_controls": {
            "model_allocation": suite.get("model_allocation"),
            "agent_ids": {
                "coordinator": suite.get("defaults", {}).get("coordinator_agent_id"),
                "solo": suite.get("defaults", {}).get("solo_agent_id"),
                "retriever": suite.get("defaults", {}).get("retriever_agent_id"),
                "specialists": [
                    item.get("agent_id") for item in suite.get("defaults", {}).get("analysts", [])
                ],
            },
            "execution_controls": suite.get("execution_controls"),
        },
        "files": {
            "suite": file_record(suite_path),
            "source_lock": file_record(source_lock_path),
            "protocol": file_record(protocol_path),
            "prompt_and_grader_source": file_record(prompt_grader_path),
            "agent_source": file_record(agent_source_path),
            "executable": file_record(executable_path),
        },
        "environment": {
            "os": platform.platform(),
            "architecture": platform.machine(),
            "go_version": command_output(["go", "version"], repo_root),
            "git_commit": command_output(["git", "rev-parse", "HEAD"], repo_root),
            "git_worktree_clean": command_output(["git", "status", "--porcelain"], repo_root) == "",
        },
    }
    if report_path is not None:
        manifest["files"]["report"] = file_record(report_path)
    assert_secret_free(manifest)
    return manifest


def validate_model_allocation(report: dict[str, Any], suite: dict[str, Any]) -> None:
    allocation = suite.get("model_allocation", {})
    defaults = suite.get("defaults", {})
    agent_roles = {
        defaults.get("coordinator_agent_id"): "coordinator",
        defaults.get("solo_agent_id"): "solo_staged",
        defaults.get("retriever_agent_id"): "retriever",
    }
    for analyst in defaults.get("analysts", []):
        agent_roles[analyst.get("agent_id")] = "specialists"
    for case in report.get("cases", []):
        for attempt in case.get("attempts", []):
            for mode in attempt.get("modes", []):
                calls = mode.get("model_calls", [])
                if not calls:
                    raise ValueError(f"observation has no provider model telemetry: {mode.get('observation_id')}")
                for call in calls:
                    if mode.get("mode") == "team_shared_retrieval_all_pro":
                        expected = allocation.get("capacity_matched_team")
                    else:
                        expected = allocation.get(agent_roles.get(call.get("agent_id"), ""))
                    if not expected or call.get("model") != expected:
                        raise ValueError(
                            f"provider model allocation mismatch for {call.get('agent_id')}: "
                            f"{call.get('model')} != {expected}"
                        )


def rejected_formal_filename(path: Path) -> bool:
    lowered = path.name.lower()
    return any(label in lowered for label in FORBIDDEN_FORMAL_LABELS)


def validate_confirmatory_manifest(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if rejected_formal_filename(path):
        raise ValueError(f"non-confirmatory filename is prohibited: {path.name}")
    manifest = read_json(path)
    assert_secret_free(manifest)
    if manifest.get("artifact_status") != "confirmatory":
        raise ValueError(f"manifest is not confirmatory: {path}")
    if manifest.get("protocol_status") != "frozen":
        raise ValueError(f"manifest protocol is not frozen: {path}")
    report_meta = manifest.get("files", {}).get("report", {})
    report_name = report_meta.get("name", "")
    if not report_name or rejected_formal_filename(Path(report_name)):
        raise ValueError(f"report filename is not confirmatory: {report_name}")
    report_path = path.parent / report_name
    if not report_path.is_file() or sha256_file(report_path) != report_meta.get("sha256"):
        raise ValueError(f"retained report is missing or hash-mismatched: {report_path}")
    report = read_json(report_path)
    if report.get("status") != "frozen" or report.get("study") != manifest.get("study"):
        raise ValueError(f"retained report is not a frozen artifact for {manifest.get('study')}")
    return manifest, report


def mode_cost(mode: dict[str, Any]) -> float:
    return sum(float(call.get("estimated_cost_usd", 0) or 0) for call in mode.get("model_calls", []))


def grounding_accuracy(stages: dict[str, Any]) -> float:
    assertions = int(stages.get("grounding_assertions", 0) or 0)
    violations = int(stages.get("grounding_violations", 0) or 0)
    return 1.0 if assertions == 0 else max(0.0, (assertions - violations) / assertions)


def flatten_reports(reports: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for report in reports:
        for case in report.get("cases", []):
            for attempt in case.get("attempts", []):
                for mode in attempt.get("modes", []):
                    if mode.get("mode") not in PRIMARY_MODES:
                        continue
                    observation_id = mode.get("observation_id")
                    if not observation_id or observation_id in seen:
                        raise ValueError(f"missing or duplicate observation ID: {observation_id}")
                    seen.add(observation_id)
                    stages = mode.get("stages", {})
                    usage = mode.get("usage", {})
                    error = str(mode.get("error", "") or "")
                    rows.append(
                        {
                            "pair_id": attempt.get("pair_id"),
                            "observation_id": observation_id,
                            "case_id": case.get("id"),
                            "company": case.get("company"),
                            "task_family": case.get("task_family"),
                            "cluster_id": case.get("cluster_id"),
                            "corpus_load": case.get("corpus_load"),
                            "attempt": attempt.get("attempt"),
                            "mode": mode.get("mode"),
                            "order_index": mode.get("order_index"),
                            "evaluated": int(not error),
                            "errored": int(bool(error)),
                            "error": error,
                            "passed": int(bool(mode.get("passed"))) if not error else "",
                            "final_evidence_recall": stages.get("final_evidence_recall", "") if not error else "",
                            "grounding_accuracy": grounding_accuracy(stages) if not error else "",
                            "grounding_violations": stages.get("grounding_violations", "") if not error else "",
                            "latency_ms": mode.get("latency_ms", "") if not error else "",
                            "total_tokens": usage.get("total_tokens", "") if not error else "",
                            "estimated_cost_usd": mode_cost(mode) if not error else "",
                            "delegation_status_counts": json.dumps(stages.get("delegation_status_counts", {}), sort_keys=True),
                            "first_attempt_successes": stages.get("first_attempt_successes", 0),
                            "recovery_successes": stages.get("recovery_successes", 0),
                        }
                    )
    return rows


METRICS = (
    "passed",
    "final_evidence_recall",
    "grounding_accuracy",
    "grounding_violations",
    "latency_ms",
    "total_tokens",
    "estimated_cost_usd",
)


def make_pair_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_pair: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_pair[str(row["pair_id"])][str(row["mode"])] = row
    output: list[dict[str, Any]] = []
    for pair_id in sorted(by_pair):
        modes = by_pair[pair_id]
        exemplar = next(iter(modes.values()))
        pair = {key: exemplar[key] for key in ("pair_id", "case_id", "company", "task_family", "cluster_id", "corpus_load", "attempt")}
        for mode_name in PRIMARY_MODES:
            mode = modes.get(mode_name)
            pair[f"{mode_name}_present"] = int(mode is not None)
            pair[f"{mode_name}_evaluated"] = mode["evaluated"] if mode else 0
            pair[f"{mode_name}_error"] = mode["error"] if mode else "missing observation"
            pair[f"{mode_name}_delegation_status_counts"] = mode["delegation_status_counts"] if mode else "{}"
            pair[f"{mode_name}_first_attempt_successes"] = mode["first_attempt_successes"] if mode else ""
            pair[f"{mode_name}_recovery_successes"] = mode["recovery_successes"] if mode else ""
            for metric in METRICS:
                pair[f"{mode_name}_{metric}"] = mode[metric] if mode else ""
        output.append(pair)
    return output


def summarize(rows: list[dict[str, Any]], group_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in group_keys)].append(row)
    output = []
    for key, members in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        evaluated = [row for row in members if row["evaluated"]]
        summary = dict(zip(group_keys, key))
        summary.update({"attempted": len(members), "evaluated": len(evaluated), "errored": len(members) - len(evaluated)})
        for metric in METRICS:
            values = [float(row[metric]) for row in evaluated if row[metric] != ""]
            summary[f"mean_{metric}"] = statistics.fmean(values) if values else ""
            summary[f"median_{metric}"] = statistics.median(values) if values else ""
        output.append(summary)
    return output


def paired_differences(pair_rows: list[dict[str, Any]], left: str, right: str, metric: str) -> list[tuple[str, float]]:
    result = []
    for row in pair_rows:
        if not row[f"{left}_evaluated"] or not row[f"{right}_evaluated"]:
            continue
        left_value = row[f"{left}_{metric}"]
        right_value = row[f"{right}_{metric}"]
        if left_value == "" or right_value == "":
            continue
        result.append((str(row["cluster_id"]), float(left_value) - float(right_value)))
    return result


def percentile(values: list[float], probability: float) -> float:
    values = sorted(values)
    if len(values) == 1:
        return values[0]
    position = probability * (len(values) - 1)
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def cluster_bootstrap(
    differences: list[tuple[str, float]], seed: int, iterations: int
) -> dict[str, Any]:
    by_cluster: dict[str, list[float]] = defaultdict(list)
    for cluster, value in differences:
        by_cluster[cluster].append(value)
    clusters = sorted(by_cluster)
    if not clusters:
        return {"pairs": 0, "clusters": 0, "median_difference": None, "ci95": [None, None]}
    rng = random.Random(seed)
    samples = []
    for _ in range(iterations):
        selected = [rng.choice(clusters) for _ in clusters]
        values = [value for cluster in selected for value in by_cluster[cluster]]
        samples.append(float(statistics.median(values)))
    raw = [value for _, value in differences]
    return {
        "pairs": len(raw),
        "clusters": len(clusters),
        "median_difference": statistics.median(raw),
        "ci95": [percentile(samples, 0.025), percentile(samples, 0.975)],
        "iterations": iterations,
        "seed": seed,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if fieldnames:
            writer.writeheader()
            writer.writerows(rows)


def configuration_outcomes(rows: list[dict[str, Any]], repetitions: int) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["case_id"]), str(row["mode"]))].append(row)
    output = []
    for (case_id, mode), members in sorted(grouped.items()):
        evaluated = [row for row in members if row["evaluated"]]
        passed = sum(int(row["passed"]) for row in evaluated)
        exemplar = members[0]
        output.append(
            {
                "case_id": case_id,
                "company": exemplar["company"],
                "task_family": exemplar["task_family"],
                "cluster_id": exemplar["cluster_id"],
                "corpus_load": exemplar["corpus_load"],
                "mode": mode,
                "attempted": len(members),
                "evaluated": len(evaluated),
                "errored": len(members) - len(evaluated),
                "passed_attempts": passed,
                "configuration_outcome": ("pass" if passed >= 2 else "fail") if len(evaluated) == repetitions else "unavailable",
            }
        )
    return output


def failure_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        if row["errored"]:
            classification = "infrastructure_error_unreviewed"
        elif row["passed"] == 0:
            classification = "model_or_grader_failure_unreviewed"
        else:
            continue
        output.append(
            {
                "observation_id": row["observation_id"],
                "pair_id": row["pair_id"],
                "mode": row["mode"],
                "evaluated": row["evaluated"],
                "errored": row["errored"],
                "primary_classification": classification,
                "review_status": "manual_review_required",
                "error": row["error"],
                "delegation_status_counts": row["delegation_status_counts"],
                "first_attempt_successes": row["first_attempt_successes"],
                "recovery_successes": row["recovery_successes"],
            }
        )
    return output


def analyze(
    manifest_paths: list[Path], output_dir: Path, iterations: int, allow_incomplete: bool = False
) -> dict[str, Any]:
    manifests_and_reports = [validate_confirmatory_manifest(path) for path in manifest_paths]
    studies = {manifest.get("study") for manifest, _ in manifests_and_reports}
    seeds = {manifest.get("randomization_seed") for manifest, _ in manifests_and_reports}
    if len(studies) != 1 or len(seeds) != 1:
        raise ValueError("confirmatory inputs must share one study and randomization seed")
    designs = [manifest.get("design", {}) for manifest, _ in manifests_and_reports]
    expected_pairs = {design.get("expected_pair_blocks") for design in designs}
    expected_observations = {design.get("expected_primary_observations") for design in designs}
    repetitions = {design.get("repetitions") for design in designs}
    if len(expected_pairs) != 1 or len(expected_observations) != 1 or len(repetitions) != 1:
        raise ValueError("confirmatory manifests disagree on the frozen design")
    rows = flatten_reports(report for _, report in manifests_and_reports)
    pair_rows = make_pair_rows(rows)
    if not allow_incomplete:
        if len(rows) != next(iter(expected_observations)) or len(pair_rows) != next(iter(expected_pairs)):
            raise ValueError(
                f"confirmatory set is incomplete: {len(rows)} observations/{len(pair_rows)} pairs, "
                f"expected {next(iter(expected_observations))}/{next(iter(expected_pairs))}"
            )
        incomplete_pairs = [row["pair_id"] for row in pair_rows if any(not row[f"{mode}_present"] for mode in PRIMARY_MODES)]
        if incomplete_pairs:
            raise ValueError(f"confirmatory pairs are missing primary modes: {incomplete_pairs[:5]}")
    mode_summary = summarize(rows, ("mode",))
    load_summary = summarize(rows, ("corpus_load", "mode"))
    configurations = configuration_outcomes(rows, int(next(iter(repetitions))))
    failures = failure_rows(rows)
    seed = int(next(iter(seeds)))
    comparisons: dict[str, Any] = {}
    for left, right in (
        ("team_shared_retrieval", "solo_staged"),
        ("team_shared_retrieval", "team_raw_context"),
    ):
        name = f"{left}_minus_{right}"
        comparisons[name] = {
            metric: cluster_bootstrap(paired_differences(pair_rows, left, right, metric), seed, iterations)
            for metric in METRICS
        }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "pair-table.csv", pair_rows)
    write_csv(output_dir / "mode-summary.csv", mode_summary)
    write_csv(output_dir / "load-summary.csv", load_summary)
    write_csv(output_dir / "configuration-outcomes.csv", configurations)
    write_csv(output_dir / "failure-classification.csv", failures)
    write_json(output_dir / "cluster-bootstrap.json", comparisons)
    result = {
        "study": next(iter(studies)),
        "artifact_status": "confirmatory-analysis",
        "manifest_count": len(manifest_paths),
        "primary_observations": len(rows),
        "pair_blocks": len(pair_rows),
        "excluded_modes": "all modes outside the frozen primary_modes set",
        "complete": len(rows) == next(iter(expected_observations)) and len(pair_rows) == next(iter(expected_pairs)),
        "outputs": [
            "pair-table.csv",
            "mode-summary.csv",
            "load-summary.csv",
            "configuration-outcomes.csv",
            "failure-classification.csv",
            "cluster-bootstrap.json",
        ],
    }
    write_json(output_dir / "analysis.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    manifest_parser = subparsers.add_parser("manifest", help="create a pre-run freeze manifest or post-run report sidecar")
    manifest_parser.add_argument("--suite", type=Path, required=True)
    manifest_parser.add_argument("--source-lock", type=Path, required=True)
    manifest_parser.add_argument("--protocol", type=Path, required=True)
    manifest_parser.add_argument("--prompt-grader-source", type=Path, required=True)
    manifest_parser.add_argument("--agent-source", type=Path, required=True)
    manifest_parser.add_argument("--executable", type=Path, required=True)
    manifest_parser.add_argument("--report", type=Path, help="retained report to seal after execution; omit for the pre-run freeze manifest")
    manifest_parser.add_argument("--status", choices=("confirmatory", "calibration", "pilot", "diagnostic", "superseded"), required=True)
    manifest_parser.add_argument("--output", type=Path, required=True)
    analyze_parser = subparsers.add_parser("analyze", help="analyze retained confirmatory JSON only")
    analyze_parser.add_argument("--manifest", type=Path, action="append", required=True)
    analyze_parser.add_argument("--output-dir", type=Path, required=True)
    analyze_parser.add_argument("--bootstrap-iterations", type=int, default=10_000)
    analyze_parser.add_argument("--allow-incomplete", action="store_true", help="permit checkpoint analysis before all frozen observations exist")
    args = parser.parse_args()
    if args.command == "manifest":
        manifest = create_manifest(
            args.suite,
            args.source_lock,
            args.protocol,
            args.prompt_grader_source,
            args.agent_source,
            args.executable,
            args.report,
            args.status,
        )
        write_json(args.output, manifest)
        print(json.dumps({"output": str(args.output), "artifact_status": args.status}, sort_keys=True))
        return 0
    if args.bootstrap_iterations <= 0:
        raise ValueError("bootstrap iterations must be positive")
    result = analyze(args.manifest, args.output_dir, args.bootstrap_iterations, args.allow_incomplete)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
