#!/usr/bin/env python3
"""Free finance-tool preflight for ten source-disjoint three-issuer packets."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from run_thesis_event_gateway import load_plugin
from run_thesis_event_panel import HERE, PLUGIN_PATH, sha256


ALLOCATION = HERE / "results/2026-10-26-cross-workflow-packet-allocation-v1/ALLOCATION.json"
FIXTURES = HERE / "workflow_fixtures_reference_source_v1"
STOCK_SCRIPT = FIXTURES / "US-market/findata-toolkit/scripts/stock_data.py"
MAPPING = HERE / "reference_source_profit_metric_map_v1.json"


def checked(plugin, name: str, args: dict) -> dict:
    result = plugin.execute(name, args)
    if not result["ok"]:
        raise ValueError(f"{name} failed: {result['errors']}")
    return result["data"]


def run() -> dict:
    allocation = json.loads(ALLOCATION.read_text())
    slots = allocation["ready_source_disjoint_packets"]
    if len(slots) != 10:
        raise ValueError("source-disjoint allocation is not ten packets")
    with tempfile.TemporaryDirectory(prefix="cross-workflow-source-tools-") as temp:
        plugin = load_plugin().FinanceToolsPlugin()
        plugin.initialize({"stateDbPath": str(Path(temp) / "ledger.db"),
                           "finskillsPath": str(FIXTURES),
                           "evaluationFixture": True, "timeoutSeconds": 90})
        cases = []
        for slot in slots:
            symbols = [item["symbol"] for item in slot["issuers"]]
            screen = checked(plugin, "screen_stocks", {
                "market": "US", "symbols": symbols, "require_complete": False,
            })
            returned = [item["symbol"] for item in
                        screen["results"] + screen["rejected"]]
            bound = {}
            for overlap in (False, True):
                result = checked(plugin, "portfolio_policy_bound", {
                    "known_holdings_percent": {symbols[0]: 40, symbols[1]: 30},
                    "unknown_remainder_percent": 30,
                    "unknown_may_overlap_known": overlap,
                    "limit_percent": 50,
                })
                bound[str(overlap).lower()] = result
            checks = {
                "all_three_source_symbols_returned":
                    len(returned) == 3 and set(returned) == set(symbols),
                "source_locked_historical_adapter":
                    screen["offline_frozen_adapter"] is True
                    and screen["synthetic"] is False
                    and screen["not_live_market_data"] is True,
                "screen_counts_match":
                    screen["passed"] + screen["failed"] == 3,
                "all_returned_sources_hashed": all(
                    len(item["source_row_packet_sha256"]) == 64
                    and all(len(period["source_sha256"]) == 64
                            for period in item["source_periods"].values())
                    for item in screen["results"] + screen["rejected"]),
                "distinct_remainder_no_breach":
                    bound["false"]["policy_status"] == "no_breach_proven"
                    and bound["false"]["exact_hhi_available"] is False,
                "overlap_remainder_indeterminate":
                    bound["true"]["policy_status"] == "indeterminate"
                    and bound["true"]["exact_hhi_available"] is False,
            }
            cases.append({"packet_id": slot["packet_id"], "symbols": symbols,
                          "screen_passed": screen["passed"],
                          "screen_rejected": screen["failed"],
                          "rejection_reasons": {item["symbol"]: item["reason"]
                                                for item in screen["rejected"]},
                          "checks": checks,
                          "all_checks_passed": all(checks.values())})
    return {"status": "free_source_locked_screen_and_policy_tool_preflight",
            "packets": len(cases),
            "passed_packets": sum(item["all_checks_passed"] for item in cases),
            "source_freeze_sha256": allocation["source_freeze_sha256"],
            "external_provider_requests": 0, "model_observations": 0,
            "estimated_external_cost_usd": 0,
            "quality_pass": None, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite")
    result = run()
    if result["passed_packets"] != 10:
        raise AssertionError("not all source-packet tool chains passed")
    manifest = {"script_sha256": sha256(Path(__file__)),
                "adapter_sha256": sha256(STOCK_SCRIPT),
                "profit_metric_map_sha256": sha256(MAPPING),
                "allocation_sha256": sha256(ALLOCATION),
                "plugin_sha256": sha256(PLUGIN_PATH),
                "source_freeze_sha256": result["source_freeze_sha256"]}
    args.output_dir.mkdir(parents=True)
    for filename, data in (("RESULT.json", result), ("MANIFEST.json", manifest)):
        (args.output_dir / filename).write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps({key: value for key, value in result.items()
                      if key != "cases"}, indent=2))


if __name__ == "__main__":
    main()
