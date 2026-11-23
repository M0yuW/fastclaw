#!/usr/bin/env python3
"""Create an unscored, hash-checked claim-review worksheet; no model calls."""

import argparse
import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CRITERIA = HERE / "FINTECH-INFERENCE-CLAIM-GATE-v1.json"
FIELDS = ["observation_id", "case_id", "result_sha256", "criterion_id",
          "critical", "criterion", "verdict", "evidence_pointer", "reviewer_note"]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recorded_hashes(result_dir):
    records = {}
    for line in (result_dir / "RESULT-SHA256.txt").read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.strip()
        if len(digest) != 64 or name in records:
            raise ValueError("invalid or duplicate hash-list entry")
        records[name] = digest
    return records


def worksheet_rows(result_dir, criteria_path=CRITERIA):
    criteria = json.loads(criteria_path.read_text())
    if criteria.get("status") != "criteria_frozen_before_new_issuer_model_observations":
        raise ValueError("claim criteria are not pre-run frozen")
    manifest_path = result_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    expected = {f"{case_id}-r{repeat}": case_id
                for case_id, repeat in manifest["run_order"]}
    if len(expected) != 15 or set(expected.values()) != set(criteria["cases"]):
        raise ValueError("manifest does not describe the three-cluster 15-run panel")
    hashes = recorded_hashes(result_dir)
    suffix = str(manifest_path.resolve().relative_to(HERE.parent.parent))
    if hashes.get(suffix) != sha256(manifest_path):
        raise ValueError("manifest hash mismatch")
    rows = []
    results = sorted(result_dir.glob("*/result.json"))
    if len(results) != len({path.parent.name for path in results}):
        raise ValueError("duplicate observation")
    for path in results:
        observation_id = path.parent.name
        case_id = expected.get(observation_id)
        if case_id is None:
            raise ValueError(f"unplanned observation: {observation_id}")
        result = json.loads(path.read_text())
        if result.get("observation_id") != observation_id or result.get("case_id") != case_id:
            raise ValueError(f"result identity mismatch: {observation_id}")
        relative = str(path.resolve().relative_to(HERE.parent.parent))
        digest = sha256(path)
        if hashes.get(relative) != digest:
            raise ValueError(f"result hash mismatch: {observation_id}")
        for check in [*criteria["common"], *criteria["cases"][case_id]]:
            rows.append({"observation_id": observation_id, "case_id": case_id,
                         "result_sha256": digest, "criterion_id": check["id"],
                         "critical": "yes" if check["critical"] else "no",
                         "criterion": check["criterion"], "verdict": "",
                         "evidence_pointer": "", "reviewer_note": ""})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()
    if args.output_csv.exists():
        parser.error("output CSV already exists; refusing to overwrite")
    rows = worksheet_rows(args.results_dir)
    if not rows:
        parser.error("no scored observations exist; no worksheet created")
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.output_csv.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"observations": len({row["observation_id"] for row in rows}),
                      "criteria_rows": len(rows), "model_calls": 0}))


if __name__ == "__main__":
    main()
