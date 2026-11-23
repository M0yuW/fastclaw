#!/usr/bin/env python3
"""Run the separately frozen, same-quarter NKE addendum without altering panel v1."""

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from run_thesis_event_panel import execute_case
from test_thesis_event_integration import HERE, ROOT, PLUGIN_PATH, locked_episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    suite_path = HERE / "thesis_event_same_quarter_addendum_v1.json"
    suite = json.loads(suite_path.read_text())
    assert suite["suite_id"] == "thesis-event-same-quarter-addendum-v1"
    assert len(suite["cases"]) == 1
    case = suite["cases"][0]
    before, _ = locked_episode(case["baseline_episode"])
    after, _ = locked_episode(case["event_episode"])
    assert before["symbol"] == after["symbol"] == case["symbol"]
    assert set(case["baseline_metrics"]) <= {item["id"] for item in before["facts"]}
    assert set(case["event_metrics"]) <= {item["id"] for item in after["facts"]}
    args.output_dir.mkdir(parents=True)
    manifest = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in [suite_path, Path(__file__), HERE / "run_thesis_event_panel.py",
                             HERE / "evidence.json", HERE / "source-lock.json", PLUGIN_PATH]}
    manifest["gateway_binary_sha256"] = hashlib.sha256(args.gateway_binary.read_bytes()).hexdigest()
    manifest["gateway_template_db_sha256"] = hashlib.sha256(args.template_db.read_bytes()).hexdigest()
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="thesis-addendum-") as temporary_root:
        result, home = execute_case(case, suite, args.template_db, args.gateway_binary, temporary_root)
        case_dir = args.output_dir / case["id"]
        case_dir.mkdir()
        (case_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        shutil.copy2(home / "finance-tools.db", case_dir / "finance-tools.db")
    print(json.dumps({"case_id": case["id"], "status": result["status"],
                      "error": result["error"], "checks": result["checks"],
                      "estimated_cost_usd": result["estimated_cost_usd"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
