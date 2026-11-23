#!/usr/bin/env python3
"""Derive and freeze the separate v2 suite from the immutable v1 input packet."""

from __future__ import annotations

import json

from evals.finance_e2e import run_stage2_project_report as v1
from evals.finance_e2e import run_stage2_project_report_v2 as v2  # sets v2 paths
from evals.finance_e2e.stage2_artifacts import create_manifest, read_json, sha256_file, write_json


def main() -> None:
    source = v1.ROOT / "evals" / "finance-retrieval-stage2a-project-report-frozen-2026-10-10.json"
    old_freeze = read_json(v1.ROOT / "evals" / "finance_e2e" / "results" /
                           "2026-10-10-stage2a-project-report-confirmatory" / "freeze.manifest.json")
    if sha256_file(source) != old_freeze["files"]["suite"]["sha256"]:
        raise ValueError("v1 source suite no longer matches its original freeze")

    suite = read_json(source)
    suite["study"] = v2.runner.STUDY
    suite["name"] = "finance-sec-retrieval-stage2a-project-report-v2"
    suite["description"] = "Frozen Stage 2A v2: runtime-bound specialist evidence and fail-fast delegation."
    suite["prompt_version"] = "finance-retrieval-stage2a-prompt-v2-runtime-bound-evidence"
    suite["execution_controls"]["delegation_evidence_transport"] = "runtime-bound"
    suite["execution_controls"]["tool_argument_validation"] = "fail-fast"
    suite["execution_controls"]["server_timeout_policy"] = "deadline-minus-grace"
    target = v2.runner.SUITE
    if target.exists():
        if read_json(target) != suite:
            raise ValueError(f"existing v2 frozen suite differs: {target}")
    else:
        write_json(target, suite)

    output = v2.runner.OUTPUT_DIR
    executable = output / "fastclaw"
    if not executable.is_file():
        raise ValueError(f"build revised Go executable first: {executable}")
    manifest_path = output / "freeze.manifest.json"
    if manifest_path.exists():
        v2.runner.check_freeze(suite, executable)
        raise ValueError("v2 is already frozen; do not regenerate its manifest")
    manifest = create_manifest(
        target, v2.runner.SOURCE_LOCK, v2.runner.PROTOCOL,
        v2.runner.ROOT / "internal/eval/finance_retrieval.go",
        v2.runner.ROOT / "internal/agent/tools/subagent.go",
        executable, None, "confirmatory", v2.runner.OWNER_REVIEW,
    )
    write_json(manifest_path, manifest)
    print(json.dumps({"suite": str(target), "manifest": str(manifest_path), "study": suite["study"]}))


if __name__ == "__main__":
    main()
