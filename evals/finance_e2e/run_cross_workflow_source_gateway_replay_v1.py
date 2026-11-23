#!/usr/bin/env python3
"""Free scripted Gateway replay of one source-locked screen and risk diagnostic.

The local provider selects fixed tools; this verifies transport and state, not
model judgment or financial-insight quality.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from pathlib import Path

from preflight_cross_workflow_source_tools_v1 import ALLOCATION, FIXTURES, MAPPING, STOCK_SCRIPT
from run_finance_gateway_fault_replay import ScriptedProvider, configure_provider, text_stream, tool_stream
from run_finance_workflow_pilot import Pilot, start_gateway, stop_gateway
from run_postcorrection_gateway_replay_v2 import gateway_turn
from run_thesis_event_panel import HERE, PLUGIN_PATH, sha256

FREEZE = HERE / "results/2026-10-26-reference-source-qualified-freeze-v1/MANIFEST.json"


def configure_frozen_screen(home: Path) -> None:
    with sqlite3.connect(home / "fastclaw.db") as db:
        row = db.execute("SELECT id,data FROM configs WHERE kind='setting' AND scope='system' AND name='plugins'").fetchone()
        settings = json.loads(row[1])
        config = settings["entries"]["finance-tools"].setdefault("config", {})
        config.update(finskillsPath=str(FIXTURES), evaluationFixture=True, timeoutSeconds=90)
        db.execute("UPDATE configs SET data=? WHERE id=?", (json.dumps(settings), row[0]))


def run(template_db: Path, binary: Path) -> dict:
    packet = json.loads(ALLOCATION.read_text())["ready_source_disjoint_packets"][0]
    freeze = json.loads(FREEZE.read_text())
    symbols = [item["symbol"] for item in packet["issuers"]]
    assert symbols == ["RJF", "CLVT", "FHN"]
    with tempfile.TemporaryDirectory(prefix="cross-workflow-scripted-gateway-") as temp:
        pilot = Pilot("cross-workflow-source-replay", template_db, binary, temp, False, 0.0)
        configure_frozen_screen(pilot.home)
        responses = [
            tool_stream("screen", "finance-tools__screen_stocks", {
                "market": "US", "symbols": symbols, "require_complete": False,
            }),
            tool_stream("save", "finance-tools__thesis_save", {
                "market": "US", "symbol": "RJF", "title": "Historical source-screen research candidate",
                "thesis": "Selected Q3 versus Q2 reported profit increased; this is a preliminary research priority, not a valuation or trading conclusion.",
                "status": "active", "conviction": 2,
                "assumptions": ["The selected SEC rows are comparable only within RJF."],
                "invalidations": ["Full filing review contradicts selected-row interpretation."],
                "evidence": [{"id": "source-row-packet", "sha256": freeze["packets"]["RJF"]["sha256"]}],
            }),
            tool_stream("risk", "finance-tools__portfolio_policy_bound", {
                "known_holdings_percent": {symbols[0]: 40, symbols[1]: 30},
                "unknown_remainder_percent": 30,
                "unknown_may_overlap_known": True, "limit_percent": 50,
            }),
            text_stream("Historical screen yielded one preliminary RJF thesis; the overlapping unknown portfolio remainder makes the 50% limit indeterminate. No trade was placed."),
        ]
        with ScriptedProvider(responses) as provider:
            configure_provider(pilot.home, provider.url)
            process, log = start_gateway(pilot.home)
            try:
                reply = gateway_turn(pilot,
                    "For packet XW-01, use the frozen historical SEC adapter to screen RJF, CLVT, and FHN with require_complete=false. This is not live market data. Save only a preliminary research thesis for a retained candidate. Then assess a portfolio with RJF 40%, CLVT 30%, unknown remainder 30% that may overlap known holdings, against a 50% single-name limit. Do not trade.",
                    "XW-01")
            finally:
                stop_gateway(process, log)
            requests = provider.requests
            unused = len(provider.responses)
        state = pilot.ledger_state()
    trace = reply.get("fastclaw", {}).get("trace", [])
    calls = [item for item in trace if item.get("type") == "tool_call"]
    results = [item for item in trace if item.get("type") == "tool_result"]
    result_text = json.dumps(results, ensure_ascii=False)
    checks = {
        "four_local_provider_requests": len(requests) == 4 and unused == 0,
        "three_tool_calls_paired": len(calls) == len(results) == 3 and
            {item["id"] for item in calls} == {item["id"] for item in results},
        "actual_screen_tool_returned_source_locked_data":
            "REFERENCE-SOURCE-HISTORICAL-PROFIT-SCREEN-v1" in result_text and
            "not_live_market_data" in result_text,
        "actual_policy_tool_returned_indeterminate": "indeterminate" in result_text,
        "one_preliminary_thesis_only": len(state["theses"]) == 1 and
            state["theses"][0]["thesis"]["symbol"] == "RJF",
        "no_alert_or_trade": not state["alerts"] and all("trade" not in item.get("name", "") for item in calls),
    }
    return {"status": "free_scripted_cross_workflow_gateway_replay",
            "packet_id": "XW-01", "checks": checks, "all_checks_passed": all(checks.values()),
            "model_observations": 0, "external_provider_requests": 0,
            "estimated_external_cost_usd": 0, "quality_pass": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite")
    result = run(args.template_db, args.gateway_binary)
    if not result["all_checks_passed"]:
        raise AssertionError(json.dumps(result["checks"], indent=2))
    manifest = {"script_sha256": sha256(Path(__file__)),
                "allocation_sha256": sha256(ALLOCATION),
                "adapter_sha256": sha256(STOCK_SCRIPT),
                "metric_map_sha256": sha256(MAPPING),
                "source_freeze_sha256": sha256(FREEZE),
                "plugin_sha256": sha256(PLUGIN_PATH),
                "gateway_binary_sha256": sha256(args.gateway_binary),
                "template_db_sha256": sha256(args.template_db),
                "provider": "local_scripted_loopback_no_external_api"}
    args.output_dir.mkdir(parents=True)
    for name, data in (("RESULT.json", result), ("MANIFEST.json", manifest)):
        (args.output_dir / name).write_text(json.dumps(data, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
