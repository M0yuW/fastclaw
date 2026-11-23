#!/usr/bin/env python3
"""Run frozen Stage 2A in resumable case batches with a cost stop."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.finance_e2e.stage2_artifacts import create_manifest, write_json


SUITE = ROOT / "evals" / "finance-retrieval-stage2a-project-report-frozen-2026-10-10.json"
SOURCE_LOCK = ROOT / "evals" / "finance_e2e" / "source-lock.json"
PROTOCOL = ROOT / "evals" / "finance_e2e" / "STAGE2-PROJECT-REPORT-AMENDMENT-2026-10-10.md"
OWNER_REVIEW = ROOT / "evals" / "finance_e2e" / "stage2-owner-review-2026-10-10.json"
OUTPUT_DIR = ROOT / "evals" / "finance_e2e" / "results" / "2026-10-10-stage2a-project-report-confirmatory"
STUDY = "finance-sec-retrieval-stage2a-project-report-v1"
STEM_PREFIX = "2026-10-10-stage2a"
BASE_URL = "http://127.0.0.1:18955"
AGENTS = (
    "finance-coordinator", "finance-solo", "finance-retriever",
    "finance-trend", "finance-accounting", "finance-risk",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_freeze(suite: dict, executable: Path) -> None:
    frozen = json.loads((OUTPUT_DIR / "freeze.manifest.json").read_text(encoding="utf-8"))
    paths = {
        "suite": SUITE,
        "source_lock": SOURCE_LOCK,
        "protocol": PROTOCOL,
        "prompt_and_grader_source": ROOT / "internal/eval/finance_retrieval.go",
        "agent_source": ROOT / "internal/agent/tools/subagent.go",
        "executable": executable,
        "freeze_audit_summary": OWNER_REVIEW,
    }
    for key, path in paths.items():
        if sha256(path) != frozen["files"][key]["sha256"]:
            raise ValueError(f"frozen input changed: {key}")
    if suite.get("study") != frozen["study"] or suite.get("status") != "frozen":
        raise ValueError("study or frozen status changed")


def make_ephemeral_key(database: Path) -> str:
    token = "fc_" + secrets.token_hex(32)
    key_id = "k_stage2_" + secrets.token_hex(8)
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT user_id FROM agents WHERE id='finance-coordinator'").fetchone()
        if row is None:
            raise ValueError("finance coordinator is absent from isolated Gateway")
        user_id = row[0]
        owners = connection.execute(
            f"SELECT id,user_id FROM agents WHERE id IN ({','.join('?' for _ in AGENTS)})", AGENTS
        ).fetchall()
        if len(owners) != len(AGENTS) or any(owner != user_id for _, owner in owners):
            raise ValueError("finance agents are missing or cross-tenant")
        connection.execute(
            "INSERT INTO apikeys(id,user_id,name,key_hash,key_prefix) VALUES (?,?,?,?,?)",
            (key_id, user_id, "stage2-project-report", hashlib.sha256(token.encode()).hexdigest(), token[:10]),
        )
        connection.executemany(
            "INSERT INTO apikey_agents(apikey_id,agent_id) VALUES (?,?)",
            [(key_id, agent_id) for agent_id in AGENTS],
        )
    return token


def report_cost(report: dict) -> float:
    return sum(
        float(call.get("estimated_cost_usd", 0) or 0)
        for case in report.get("cases", [])
        for attempt in case.get("attempts", [])
        for mode in attempt.get("modes", [])
        for call in mode.get("model_calls", [])
    )


def report_errors(report: dict) -> list[str]:
    return [
        str(mode["error"])
        for case in report.get("cases", [])
        for attempt in case.get("attempts", [])
        for mode in attempt.get("modes", [])
        if mode.get("error")
    ]


def uncertain_cost_observations(report: dict) -> list[str]:
    uncertain: list[str] = []
    for case in report.get("cases", []):
        for attempt in case.get("attempts", []):
            for mode in attempt.get("modes", []):
                calls = mode.get("model_calls", [])
                if (mode.get("error") and not calls) or any(
                    call.get("cost_uncertain") or call.get("priced") is False for call in calls
                ):
                    uncertain.append(str(mode.get("observation_id", "unknown")))
    return uncertain


def completed_cost(acknowledged_uncertain: set[str] | None = None) -> tuple[float, int, int]:
    acknowledged_uncertain = acknowledged_uncertain or set()
    cost = 0.0
    attempted = 0
    errors = 0
    seen_uncertain: set[str] = set()
    for path in sorted(OUTPUT_DIR.glob("*-confirmatory.json")):
        report = json.loads(path.read_text(encoding="utf-8"))
        uncertain = set(uncertain_cost_observations(report))
        unacknowledged = uncertain - acknowledged_uncertain
        if unacknowledged:
            raise ValueError(
                f"completed report has unmetered provider cost; do not resume automatically: {sorted(unacknowledged)[:3]}"
            )
        seen_uncertain.update(uncertain)
        cost += report_cost(report)
        modes = [mode for case in report.get("cases", []) for attempt in case.get("attempts", []) for mode in attempt.get("modes", [])]
        attempted += len(modes)
        errors += sum(bool(mode.get("error")) for mode in modes)
    if seen_uncertain != acknowledged_uncertain:
        raise ValueError(f"acknowledged uncertain observations do not match retained reports: {sorted(acknowledged_uncertain - seen_uncertain)}")
    return cost, attempted, errors


def run_batch(executable: Path, token: str, case_id: str, modes: str | None, label: str) -> tuple[float, int, int]:
    stem = f"{STEM_PREFIX}-{case_id.lower()}-{label}-20260802-confirmatory"
    report_path = OUTPUT_DIR / f"{stem}.json"
    manifest_path = OUTPUT_DIR / f"{stem}.manifest.json"
    if report_path.exists():
        if not manifest_path.exists():
            raise ValueError(f"existing report has no manifest; inspect before resume: {report_path}")
        return 0.0, 0, 0
    command = [
        str(executable), "eval", "finance-retrieval", "run", str(SUITE),
        "--base-url", BASE_URL, "--case", case_id,
        "--format", "json", "--output", str(report_path),
    ]
    if modes is not None:
        command.extend(("--mode", modes))
    environment = os.environ.copy()
    environment["FASTCLAW_API_KEY"] = token
    completed = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
    if completed.returncode != 0:
        message = completed.stderr[-1000:].replace(token, "[redacted]")
        raise RuntimeError(f"case {case_id} {label} exited {completed.returncode}: {message}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("study") != STUDY or report.get("status") != "frozen":
        raise ValueError(f"report study/status mismatch: {report_path}")
    manifest = create_manifest(
        SUITE, SOURCE_LOCK, PROTOCOL, ROOT / "internal/eval/finance_retrieval.go",
        ROOT / "internal/agent/tools/subagent.go", executable, report_path,
        "confirmatory", OWNER_REVIEW,
    )
    write_json(manifest_path, manifest)
    uncertain = uncertain_cost_observations(report)
    if uncertain:
        raise ValueError(
            f"case {case_id} has unmetered provider cost; inspect before further spending: {uncertain[:3]}"
        )
    modes_seen = [mode for case in report["cases"] for attempt in case["attempts"] for mode in attempt["modes"]]
    errors = report_errors(report)
    return report_cost(report), len(modes_seen), len(errors)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="isolated Gateway database snapshot")
    parser.add_argument("--max-new-cases", type=int, default=24)
    parser.add_argument("--max-estimated-usd", type=float, default=10.0)
    parser.add_argument("--prior-estimated-usd", type=float, default=0.0,
                        help="non-overlapping estimated cost already incurred before this study")
    parser.add_argument("--acknowledge-uncertain-observation", action="append", default=[],
                        help="exact retained observation ID inspected before resumption")
    parser.add_argument("--uncertain-reserve-usd", type=float, default=0.0,
                        help="conservative cost reserve for acknowledged unmetered calls")
    parser.add_argument("--prior-report", type=Path, action="append", default=[])
    args = parser.parse_args()
    executable = OUTPUT_DIR / "fastclaw"
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    check_freeze(suite, executable)
    if args.prior_estimated_usd < 0:
        raise ValueError("prior estimated cost cannot be negative")
    if args.uncertain_reserve_usd < 0:
        raise ValueError("uncertain cost reserve cannot be negative")
    acknowledged = set(args.acknowledge_uncertain_observation)
    if len(acknowledged) != len(args.acknowledge_uncertain_observation):
        raise ValueError("duplicate uncertain observation acknowledgment")
    if bool(acknowledged) != bool(args.uncertain_reserve_usd):
        raise ValueError("uncertain observation acknowledgment requires a positive cost reserve, and vice versa")
    prior_cost = args.prior_estimated_usd + args.uncertain_reserve_usd + sum(
        report_cost(json.loads(path.read_text(encoding="utf-8"))) for path in args.prior_report
    )
    spent, attempted, errors = completed_cost(acknowledged)
    token = make_ephemeral_key(args.database)
    started = time.monotonic()
    new_cases = 0
    print(f"resume: formal_cost_usd={spent:.6f} prior_cost_usd={prior_cost:.6f} observations={attempted} errors={errors}", flush=True)
    for case in suite["cases"]:
        case_id = case["id"]
        if new_cases >= args.max_new_cases:
            break
        if spent + prior_cost >= args.max_estimated_usd - 0.5:
            print("STOP: budget guard before next case", flush=True)
            break
        if time.monotonic() - started > 12 * 3600:
            print("STOP: twelve-hour checkpoint", flush=True)
            break
        cost, n, e = run_batch(executable, token, case_id, None, "primary-diagnostic")
        if n:
            new_cases += 1
            spent += cost
            attempted += n
            errors += e
            print(f"case={case_id} observations={n} errors={e} batch_usd={cost:.6f} total_usd={spent+prior_cost:.6f}", flush=True)
        if attempted and errors / attempted > 0.05:
            print("STOP: infrastructure error rate exceeds five percent", flush=True)
            break
    else:
        for case_id in suite["ablation_case_ids"]:
            if spent + prior_cost >= args.max_estimated_usd - 0.5:
                print("STOP: budget guard before ablation", flush=True)
                break
            cost, n, e = run_batch(executable, token, case_id, "team_shared_retrieval_all_pro", "ablation")
            spent += cost
            attempted += n
            errors += e
            if n:
                print(f"ablation={case_id} observations={n} errors={e} batch_usd={cost:.6f} total_usd={spent+prior_cost:.6f}", flush=True)
            if attempted and errors / attempted > 0.05:
                print("STOP: infrastructure error rate exceeds five percent", flush=True)
                break
    print(f"checkpoint: observations={attempted} errors={errors} estimated_total_usd={spent+prior_cost:.6f}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"STOP: {error}", file=sys.stderr, flush=True)
        raise SystemExit(1)
