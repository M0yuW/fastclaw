#!/usr/bin/env python3
"""Free HBAN fixture-correction replay; never a confirmatory model result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_postcorrection_v4_event_preflight as v4
import build_postcorrection_v5_hban_development_fixture as corrected
import run_postcorrection_v4_scripted_gateway_replay as scripted
from run_thesis_event_panel import PLUGIN_PATH, ROOT, sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    fixture = corrected.corrected_hban_fixture()
    context = fixture["numeric_context"]
    checks = {
        "audited_adjustment_in_context":
            "24 USD_million gain on sale" in context
            and "adjusted sequential increase 133 USD_million" in context,
        "adjustment_reaches_prompt": False,
    }
    original_prompt = v4.review_prompt

    def checked_prompt(item: dict, thesis_id: str, alert_id: str) -> str:
        prompt = original_prompt(item, thesis_id, alert_id)
        checks["adjustment_reaches_prompt"] = (
            "24 USD_million gain on sale" in prompt
            and "adjusted sequential increase 133 USD_million" in prompt
        )
        return prompt

    v4.review_prompt = checked_prompt
    try:
        replay = scripted.run(
            args.template_db, args.gateway_binary, "HBAN",
            {"fixtures": [fixture], "ready_cases": 1,
             "rendered_signed_bridges": fixture["bridge_count"]},
        )
    finally:
        v4.review_prompt = original_prompt
    checks.update(replay["checks"])
    result = {
        "status": "development_only_seen_v4_case_not_confirmatory",
        "case_id": fixture["case_id"],
        "checks": checks,
        "all_checks_passed": all(checks.values()),
        "model_observations": 0,
        "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
    }
    paths = [Path(__file__), Path(corrected.__file__), Path(v4.__file__),
             Path(scripted.__file__), v4.FIRST_PACKETS["HBAN"], PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api",
                    selected_symbol="HBAN", model_observations=0)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "result.json").write_text(
        json.dumps(result, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in (args.output_dir / "manifest.json",
                     args.output_dir / "result.json")))
    print(json.dumps(result, indent=2))
    if not result["all_checks_passed"]:
        raise AssertionError("HBAN development replay failed")


if __name__ == "__main__":
    main()
