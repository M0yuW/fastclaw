#!/usr/bin/env python3
"""Generate and verify the content-addressed thesis evidence entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "evals" / "thesis-evidence-manifest.json"
FORBIDDEN_PRIMARY = ("calibration", "diagnostic", "superseded")

GROUPS = {
    "fixed_evidence_confirmatory": [
        ("evals/multiagent-finance-runtime.yaml", "suite"),
        ("finance-runtime-formal-r5.json", "raw_report"),
        ("evals/finance-runtime-formal-r5.md", "summary"),
        ("evals/finance-runtime-formal-r5.manifest.json", "sub_manifest"),
        ("project-report/finance_reanalysis.json", "analysis"),
        ("project-report/analysis/main.go", "analysis_source"),
        ("project-report/analysis/main_test.go", "analysis_test"),
    ],
    "sec_hard_r3_confirmatory": [
        ("evals/multiagent-finance-sec-hard.json", "suite"),
        ("evals/finance_e2e/source-lock.json", "source_lock"),
        ("evals/finance_e2e/acceptance-time-lock.json", "acceptance_time_lock"),
        ("evals/finance_e2e/results/2026-08-02-hard-r3-final.json", "raw_report"),
        ("evals/finance_e2e/results/2026-08-02-hard-r3-final-analysis.json", "analysis"),
        ("evals/finance_e2e/results/2026-08-02-hard-r3-final-summary.md", "summary"),
        ("evals/finance_e2e/analyze_report.py", "grader_analysis_source"),
        ("evals/finance_e2e/build_hard_suite.py", "suite_generator"),
    ],
    "retrieval_descriptive_pilot": [
        ("evals/finance-retrieval-sec.json", "suite"),
        ("evals/finance_e2e/source-lock.json", "source_lock"),
        ("evals/finance_e2e/acceptance-time-lock.json", "acceptance_time_lock"),
        ("evals/finance_e2e/evidence.json", "human_oracle"),
        ("evals/finance_e2e/gold-fact-provenance.json", "fact_provenance"),
        ("evals/finance_e2e/gold-fact-provenance.csv", "fact_provenance_table"),
        ("evals/finance_e2e/gold-derived-provenance.json", "derived_provenance"),
        ("evals/finance_e2e/gold-derived-provenance.csv", "derived_provenance_table"),
        ("evals/finance_e2e/build_provenance.py", "provenance_generator"),
        ("evals/finance_e2e/results/2026-08-02-retrieval-pilot-v8-nvda-medium-final.json", "raw_report"),
        ("evals/finance_e2e/results/2026-08-02-retrieval-pilot-v9-nvda-medium-baselines.json", "raw_report"),
        ("evals/finance_e2e/results/2026-08-02-retrieval-pilot-v10-nvda-medium-raw-trace.json", "raw_report"),
        ("evals/finance_e2e/results/2026-08-02-retrieval-pilot-final-summary.md", "summary"),
        ("evals/finance_e2e/results/2026-08-02-retrieval-pilot-final.manifest.json", "sub_manifest"),
    ],
    "stage2_proposed": [
        ("evals/finance-retrieval-stage2a-v2.json", "draft_suite"),
        ("evals/finance_e2e/STAGE2-EXPERIMENT-PROTOCOL.md", "draft_protocol"),
        ("evals/finance_e2e/stage2_artifacts.py", "analysis_source"),
        ("evals/finance_e2e/stage2_freeze_audit.py", "audit_source"),
        ("evals/finance_e2e/build_stage2_suite.py", "suite_generator"),
        ("evals/finance_e2e/stage2-freeze-audit-draft/audit-tasks.csv", "human_audit_tasks"),
        ("evals/finance_e2e/stage2-freeze-audit-draft/machine-reference.csv", "sealed_machine_reference"),
        ("evals/finance_e2e/stage2-freeze-audit-draft/README.md", "human_audit_instructions"),
        ("project-report/fastclaw_project_report.md", "thesis_source"),
    ],
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(root: Path, relative: str, role: str, status: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise ValueError(f"missing thesis evidence: {relative}")
    return {"path": relative, "role": role, "artifact_status": status, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def build_manifest(root: Path = ROOT) -> dict[str, Any]:
    groups = []
    for status, entries in GROUPS.items():
        groups.append({"artifact_status": status, "files": [record(root, path, role, status) for path, role in entries]})
    return {
        "schema_version": 1,
        "purpose": "single content-addressed entrypoint for thesis evidence and proposed Stage 2 materials",
        "replay_boundary": "offline tables and graders are reproducible; historical provider trajectories are not",
        "groups": groups,
        "excluded_from_confirmatory_analysis": ["calibration", "pilot", "diagnostic", "superseded"],
        "verification_command": "python3 evals/finance_e2e/thesis_evidence_manifest.py --check",
    }


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verify(manifest: dict[str, Any], root: Path = ROOT) -> None:
    seen: set[tuple[str, str]] = set()
    for group in manifest.get("groups", []):
        status = str(group.get("artifact_status", ""))
        for item in group.get("files", []):
            path = str(item.get("path", ""))
            key = (status, path)
            if key in seen:
                raise ValueError(f"duplicate evidence entry: {status}:{path}")
            seen.add(key)
            if "confirmatory" in status and any(label in path.lower() for label in FORBIDDEN_PRIMARY):
                raise ValueError(f"status mixing in confirmatory group: {path}")
            absolute = root / path
            if not absolute.is_file():
                raise ValueError(f"missing thesis evidence: {path}")
            if absolute.stat().st_size != item.get("bytes") or sha256_file(absolute) != item.get("sha256"):
                raise ValueError(f"hash drift in thesis evidence: {path}")
    r5 = read_json(root / "evals/finance-runtime-formal-r5.manifest.json")
    if sha256_file(root / r5["artifact"]) != r5["artifact_sha256"] or sha256_file(root / r5["suite"]) != r5["suite_sha256"]:
        raise ValueError("r5 sub-manifest hash chain failed")
    pilot = read_json(root / "evals/finance_e2e/results/2026-08-02-retrieval-pilot-final.manifest.json")
    linked = [pilot["suite"], pilot["source_lock"], pilot["summary"], *pilot["final_observations"]]
    for item in linked:
        if sha256_file(root / item["path"]) != item["sha256"]:
            raise ValueError(f"retrieval Pilot sub-manifest hash chain failed: {item['path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        manifest = read_json(args.output)
        verify(manifest)
        if manifest != build_manifest():
            raise ValueError("thesis evidence manifest is stale")
        print("Thesis evidence manifest and sub-manifest hash chains are valid")
        return 0
    manifest = build_manifest()
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verify(manifest)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
