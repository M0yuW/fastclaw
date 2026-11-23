#!/usr/bin/env python3
"""Local-scripted Gateway A/B for two guardable errors and two controls."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import run_reference_precommit_gateway_ab_v1 as gateway_ab
from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_thesis_event_panel import PLUGIN_PATH, ROOT, sha256


CASES = (
    "J-b6e559adea6c6abb",  # BOKF false hold assurance
    "J-bf4eba69527e01ab",  # TOST reversed signed tax contribution
    "J-12d921bb4b32208c",  # MQ correctly blocked control
    "J-d9ea0e54a3a5b5f4",  # EFX wrong prose already blocked
)
VETO_SYMBOLS = frozenset({"BOKF", "TOST"})


def run(template_db: Path, binary: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise ValueError("output path exists; refusing to overwrite")
    fixtures = {item["runtime_symbol"]: item for item in preflight()["fixtures"]}
    output_dir.mkdir(parents=True)
    gateway_ab.VETO_SYMBOLS = VETO_SYMBOLS
    results = []
    with tempfile.TemporaryDirectory(prefix="reference-guard-gateway-ab-v2-") as temp:
        for masked_id in CASES:
            packet = json.loads((gateway_ab.JUDGMENTS / "masked_packets" /
                                 f"{masked_id}.json").read_text())
            fixture = fixtures[packet["source_packet"]["symbol"]]
            for branch in ("A", "B"):
                result = gateway_ab._run_arm(template_db, binary, fixture,
                                             packet, branch, Path(temp), output_dir)
                symbol = fixture["runtime_symbol"]
                if symbol == "EFX":
                    result["checks"]["bad_deferred_prose_sanitized_only_in_guard_arm"] = (
                        result["review_rationale_guard_sanitized"] == (branch == "B")
                        and result["review_rationale_matches_original"] ==
                            (branch == "A"))
                if symbol == "MQ":
                    result["checks"]["good_deferred_prose_preserved"] = (
                        result["review_rationale_matches_original"]
                        and not result["review_rationale_guard_sanitized"])
                result["all_checks_passed"] = all(result["checks"].values())
                results.append(result)
    summary = {
        "study_type": "developmental_scripted_gateway_precommit_ab_v2",
        "branches": len(results),
        "all_checks_passed": all(item["all_checks_passed"] for item in results),
        "model_observations": 0, "external_provider_requests": 0,
        "estimated_external_cost_usd": 0, "quality_pass": None,
        "results": results,
        "interpretation_boundary": "Saved calls and local scripted provider only; seen-case mechanism check, not prospective guard accuracy or financial insight quality.",
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {
        "gateway_binary_sha256": sha256(binary),
        "gateway_template_db_sha256": sha256(template_db),
        "plugin_sha256": sha256(PLUGIN_PATH),
        "guard_sha256": sha256(ROOT / "plugins/finance-tools/review_arithmetic_guard.py"),
        "v1_helper_script_sha256": sha256(Path(gateway_ab.__file__)),
        "script_sha256": sha256(Path(__file__)),
        "provider": "local_scripted_loopback_no_external_api",
    }
    (output_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    paths = sorted([output_dir / "SUMMARY.json", output_dir / "MANIFEST.json",
                    *output_dir.glob("*/*/trace.json"),
                    *output_dir.glob("*/*/finance-tools.db")])
    (output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output_dir)}\n" for path in paths))
    if not summary["all_checks_passed"]:
        raise AssertionError("scripted Gateway review-guard v2 replay failed")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    print(json.dumps(run(args.template_db, args.gateway_binary, args.output_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
