#!/usr/bin/env python3
"""Free v4 source-fixture Gateway seam replay using an isolated scripted provider.

This verifies fixture delivery, tool writes and ledger state, not model quality.
It never sends a request to DeepSeek or another external model.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import run_postcorrection_gateway_replay_v2 as replay
from run_thesis_event_panel import ROOT, sha256


HERE = Path(__file__).resolve().parent


def run(template_db: Path, binary: Path, symbol: str,
        prepared: dict | None = None) -> dict:
    prepared = prepared if prepared is not None else source_batch.preflight()
    if symbol not in {item["runtime_symbol"] for item in prepared["fixtures"]}:
        raise ValueError("symbol is not in source-audited v4 frame")
    original_builder = replay.source_batch.review_prompt
    original_call = replay.must_call

    def v4_call(finance, name, arguments, tenant):
        if name == "watchlist_save" and symbol == "C":
            arguments = {**arguments, "keywords": [source_batch.watchlist_keyword(symbol)]}
        return original_call(finance, name, arguments, tenant)

    replay.source_batch.review_prompt = source_batch.review_prompt
    replay.must_call = v4_call
    try:
        result = replay.run(template_db, binary, symbol, prepared["fixtures"])
    finally:
        replay.source_batch.review_prompt = original_builder
        replay.must_call = original_call
    result["status"] = "v4_local_scripted_gateway_replay_not_model_quality"
    result["source_ready_cases"] = prepared["ready_cases"]
    result["rendered_signed_bridges"] = prepared["rendered_signed_bridges"]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--symbol", choices=sorted(
        {*source_batch.FIRST_PACKETS, *source_batch.DECLARED_PACKETS}),
        default="LPLA")
    selection.add_argument("--all-ready", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    args.output_dir.mkdir(parents=True)
    symbols = (sorted({*source_batch.FIRST_PACKETS, *source_batch.DECLARED_PACKETS})
               if args.all_ready else [args.symbol])
    paths = {Path(__file__), Path(source_batch.__file__), Path(replay.__file__),
             HERE / "audit_postcorrection_v4_source_identity.py",
             HERE / "audit_v4_declared_sec_rows.py"}
    paths.update((source_batch.FIRST_PACKETS.get(symbol)
                  or source_batch.DECLARED_PACKETS[symbol]) for symbol in symbols)
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in sorted(paths)}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api",
                    selected_symbols=symbols, model_observations=0)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    prepared = source_batch.preflight()
    results = []
    for symbol in symbols:
        try:
            result = run(args.template_db, args.gateway_binary, symbol, prepared)
        except Exception as exc:
            result = {"status": "v4_local_scripted_gateway_replay_error",
                      "symbol": symbol, "error": f"{type(exc).__name__}: {exc}",
                      "checks": {}, "model_observations": 0,
                      "external_provider_requests": 0}
        results.append(result)
        name = f"result-{symbol}.json" if args.all_ready else "result.json"
        (args.output_dir / name).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"symbol": symbol,
                          "checks_passed": bool(result["checks"])
                              and all(result["checks"].values()),
                          "error": result.get("error"), "completed": len(results),
                          "planned": len(symbols), "external_provider_requests": 0}),
              flush=True)
    summary = {"status": "v4_local_scripted_gateway_replay_not_model_quality",
               "cases": len(results),
               "all_checks_passed": all(bool(item["checks"])
                                        and all(item["checks"].values())
                                        for item in results),
               "model_observations": 0, "external_provider_requests": 0,
               "estimated_external_cost_usd": 0}
    (args.output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    hash_paths = [args.output_dir / "manifest.json", args.output_dir / "SUMMARY.json",
                  *sorted(args.output_dir.glob("result*.json"))]
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in hash_paths))
    print(json.dumps(summary, indent=2))
    if not summary["all_checks_passed"]:
        raise AssertionError("v4 scripted Gateway seam replay failed")


if __name__ == "__main__":
    main()
