#!/usr/bin/env python3
"""Free local Gateway seam replay for the source-audited rich PAYO packet.

The provider is scripted loopback. This checks delivery and real finance-tool
state transitions, not the quality of any generated financial insight.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_payo_v4_rich_fixture as rich
import run_postcorrection_gateway_replay_v2 as replay
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


def run(template_db: Path, binary: Path) -> dict:
    fixture = rich.fixture()
    original_prompt = replay.source_batch.review_prompt
    original_provider = replay.local.ScriptedProvider
    providers = []

    class TrackingProvider(original_provider):
        def __init__(self, responses):
            super().__init__(responses)
            providers.append(self)

    replay.source_batch.review_prompt = rich.review_prompt
    replay.local.ScriptedProvider = TrackingProvider
    try:
        result = replay.run(template_db, binary, "PAYO", [fixture])
    finally:
        replay.source_batch.review_prompt = original_prompt
        replay.local.ScriptedProvider = original_provider
    if len(providers) != 1:
        raise ValueError("expected one isolated loopback provider")
    delivered = json.dumps(providers[0].requests, ensure_ascii=False)
    packet = json.loads(rich.source_audit.PACKET.read_text())
    required = [
        fixture["case_id"],
        fixture["event"]["sources"][0]["sha256"],
        "Source-defined GAAP change bridge",
        "non-GAAP and not interchangeable with GAAP net income",
        "Company guidance (forward-looking, not realized)",
        "Attributed management statements (source claims",
        "net-income change -5357",
        "All three residuals are zero",
    ]
    result["checks"]["host_numeric_context_reached_provider"] = all(
        item in delivered for item in required
    )
    result["checks"]["private_interpretation_checks_not_delivered"] = not any(
        item in delivered for item in packet["precommitted_interpretation_checks"]
    )
    result["checks"]["no_external_model_request"] = (
        result["model_observations"] == 0
        and result["external_provider_requests"] == 0
    )
    result["status"] = "payo_v4_rich_scripted_gateway_replay_not_model_quality"
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template database missing")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), Path(rich.__file__),
             Path(rich.source_audit.__file__), rich.source_audit.PACKET,
             Path(replay.__file__), Path(replay.local.__file__),
             HERE / "run_finance_workflow_pilot.py",
             HERE / "run_thesis_event_panel.py", PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update({
        "gateway_binary_sha256": sha256(args.gateway_binary),
        "gateway_template_db_sha256": sha256(args.template_db),
        "provider": "local_scripted_loopback_no_external_api",
        "development_symbol": "PAYO",
        "source_scope": "seen-source development fixture, not confirmatory",
    })
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    result = run(args.template_db, args.gateway_binary)
    (args.output_dir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in (args.output_dir / "manifest.json",
                     args.output_dir / "result.json")
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not all(result["checks"].values()):
        raise AssertionError("PAYO scripted Gateway replay failed")


if __name__ == "__main__":
    main()
