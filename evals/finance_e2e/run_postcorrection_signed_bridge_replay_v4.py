#!/usr/bin/env python3
"""Free local Gateway replay proving the signed bridge reaches model input.

The provider is an isolated loopback scripted server. No DeepSeek call, model
reasoning observation, or quality rating occurs here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_postcorrection_signed_bridge_fixture_v4 as bridge_fixture
import run_postcorrection_event_holdout_v2 as frozen_v2
import run_postcorrection_gateway_replay_v2 as replay
from run_thesis_event_panel import ROOT, sha256


def run(template_db: Path, binary: Path) -> dict:
    prepared = bridge_fixture.prepare()
    fixture = next(item for item in prepared["fixtures"]
                   if item["runtime_symbol"] == "ALLY")
    expected = "+86 −31 +22 = 77 USD_million"
    if expected not in fixture["numeric_context"]:
        raise ValueError("ALLY signed bridge absent from prepared numeric context")

    original_provider = replay.local.ScriptedProvider
    instances = []

    class TrackingProvider(original_provider):
        def __init__(self, responses):
            super().__init__(responses)
            instances.append(self)

    replay.local.ScriptedProvider = TrackingProvider
    try:
        result = replay.run(template_db, binary, "ALLY", prepared["fixtures"])
    finally:
        replay.local.ScriptedProvider = original_provider
    if len(instances) != 1:
        raise ValueError("expected exactly one isolated scripted provider")
    delivered = json.dumps(instances[0].requests, ensure_ascii=False)
    result["checks"].update({
        "signed_bridge_reached_model_interface":
            expected in delivered
            and "Source-defined accounting bridge for pre-tax income" in delivered
            and fixture["event"]["sources"][0]["sha256"] in delivered,
        "no_external_model_request":
            result["external_provider_requests"] == 0
            and result["model_observations"] == 0,
    })
    result["status"] = "v4_development_scripted_gateway_replay_not_model_quality"
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
        raise FileNotFoundError("Gateway binary or template DB missing")
    args.output_dir.mkdir(parents=True)
    paths = set(frozen_v2.manifest_paths())
    v4_dir = Path(__file__).parent
    paths.update({Path(__file__), Path(bridge_fixture.__file__),
                  Path(replay.__file__),
                  v4_dir / "selected_fact_signed_bridge_v4.py",
                  v4_dir / "accounting_bridge_catalog_v4.py"})
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in sorted(paths)}
    manifest.update({
        "gateway_binary_sha256": sha256(args.gateway_binary),
        "gateway_template_db_sha256": sha256(args.template_db),
        "provider": "local_scripted_loopback_no_external_api",
        "development_symbol": "ALLY",
    })
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    result = run(args.template_db, args.gateway_binary)
    (args.output_dir / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in (args.output_dir / "manifest.json", args.output_dir / "result.json")))
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not all(result["checks"].values()):
        raise AssertionError("local bridge Gateway replay failed")


if __name__ == "__main__":
    main()
