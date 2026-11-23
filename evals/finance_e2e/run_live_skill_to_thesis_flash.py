#!/usr/bin/env python3
"""One isolated live FinData Skill -> preliminary thesis Gateway experiment.

The live price series is retrieved by the agent through the Go runtime's exec
tool. The same agent session then writes a bounded research thesis through the
finance plugin. The source Gateway database is backed up, never modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
from run_thesis_event_panel import AGENT_ID, PLUGIN_PATH, ROOT, sha256, start_gateway, stop_gateway

MODEL = panel.MODEL
PRICING = panel.PRICING
CAP_USD = 0.02
SYMBOL = "AMD"


def tool_events(pilot, event_type: str, name: str) -> list[dict]:
    return [event for turn in pilot.turns
            for event in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace", [])
            if event.get("type") == event_type and event.get("name") == name]


def data_from_skill(pilot) -> dict | None:
    for event in tool_events(pilot, "tool_result", "exec"):
        try:
            data = json.loads(event.get("result") or event.get("content") or "")
        except (ValueError, TypeError):
            continue
        if (data.get("symbol") == SYMBOL and data.get("source_url")
                and data.get("interval") == "1d" and len(data.get("prices", [])) >= 2):
            return data
    return None


def text_contains(value: object, needle: str) -> bool:
    return needle.lower() in json.dumps(value, ensure_ascii=False).lower()


def skill_fetch_calls(calls: list[dict], skill_script: Path) -> list[dict]:
    matches = []
    for event in calls:
        if event.get("name") != "exec":
            continue
        try:
            command = json.loads(event.get("arguments") or "{}").get("command", "")
        except (TypeError, ValueError):
            continue
        if str(skill_script) in command and "--source nasdaq" in command:
            matches.append(event)
    return matches


def run(args: argparse.Namespace) -> dict:
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    for path in (args.template_db, args.gateway_binary, args.skill_root / "SKILL.md",
                 args.skill_root / "scripts" / "stock_data.py", args.python_exe):
        if not path.is_file():
            raise FileNotFoundError(path)
    base.MODEL, base.PRICING, base.CAP_USD = MODEL, PRICING, CAP_USD
    with tempfile.TemporaryDirectory(prefix="live-skill-thesis-") as temp_root:
        pilot = panel.PanelPilot("LIVE-SKILL-AMD", args.template_db,
                                 args.gateway_binary, temp_root, False, 0.0)
        with sqlite3.connect(pilot.home / "fastclaw.db") as db:
            row = db.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
            config = json.loads(row[0])
            # This broad preset is confined to this throw-away Gateway copy.
            # The result oracle below rejects any tool beyond exec/thesis_save.
            config.update(policy="standard", maxToolIterations=6, maxTokens=1800)
            db.execute("UPDATE agents SET config=? WHERE id=?", (json.dumps(config), AGENT_ID))
        skill_dir = pilot.home / "skills"
        skill_dir.mkdir()
        (skill_dir / "findata-toolkit").symlink_to(args.skill_root, target_is_directory=True)
        command = (f"{args.python_exe} {args.skill_root / 'scripts' / 'stock_data.py'} "
                   "AMD --history --period 5d --source nasdaq")
        process, log = start_gateway(pilot.home)
        error = None
        data = None
        try:
            pilot.turn(
                "Read-only first step of a bounded research workflow. Use the installed "
                "findata-toolkit-us Skill to retrieve AMD's dated Nasdaq daily history. "
                "Call exec exactly once with command " + json.dumps(command) +
                " and timeout 90. Do not use other tools or write any ledger state in this "
                "turn. Report the source URL, first and latest dates/closes, currency, and "
                "daily-bar interval. If retrieval fails, say so; do not invent data."
            )
            data = data_from_skill(pilot)
            if data is None:
                raise RuntimeError("no valid dated Skill tool result; thesis step blocked")
            pilot.turn(
                "Now complete the same AMD research workflow using ONLY the price history "
                "retrieved by the Skill in the preceding turn. Independently compute the "
                "first-to-latest close change with correct direction, dates and units. "
                "Check adjacent closes before making any day-to-day direction claim; "
                "omit claims not needed for the bounded conclusion. "
                "Identify what this short price window can and cannot establish. Call "
                "finance-tools__thesis_save exactly once to create one preliminary "
                "research thesis for market US, symbol AMD, status researching and "
                "conviction 1. In the structured evidence include the actual source URL, "
                "source name, first and latest bar dates, closes, price currency and "
                "daily interval; explain that earnings, valuation and forward catalysts "
                "are not verified. Do not cite SEC data you have not retrieved, create "
                "alerts, change a portfolio, or recommend a trade. If the source or dates "
                "are missing, do not save anything and explain why."
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            stop_gateway(process, log)
        state = pilot.ledger_state()
        calls = [event for turn in pilot.turns
                 for event in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace", [])
                 if event.get("type") == "tool_call"]
        results = [event for turn in pilot.turns
                   for event in ((turn.get("response") or {}).get("fastclaw") or {}).get("trace", [])
                   if event.get("type") == "tool_result"]
        tool_names = [event.get("name") for event in calls]
        thesis_rows = state["theses"]
        thesis = thesis_rows[0].get("thesis", {}) if len(thesis_rows) == 1 else {}
        if not thesis and len(thesis_rows) == 1:
            thesis = thesis_rows[0]
        evidence = thesis.get("evidence", [])
        first, latest = ((data["prices"][0], data["prices"][-1]) if data else ({}, {}))
        expected_change_pct = ((latest["close"] / first["close"] - 1) * 100
                               if first.get("close") and latest.get("close") else None)
        evidence_change = next((item.get("close_change_percent", item.get("computed_change_percent"))
                                for item in evidence if isinstance(item, dict)
                                and ("close_change_percent" in item
                                     or "computed_change_percent" in item)), None)
        script = args.skill_root / "scripts" / "stock_data.py"
        checks = {
            "source_success": data is not None,
            "skill_fetch_once": len(skill_fetch_calls(calls, script)) == 1,
            "thesis_save_once": tool_names.count("finance-tools__thesis_save") == 1,
            "only_expected_tools": set(tool_names) <= {"exec", "finance-tools__thesis_save"},
            "tool_calls_paired": sorted(event.get("id") for event in calls)
                                 == sorted(event.get("id") for event in results),
            "one_preliminary_thesis": len(thesis_rows) == 1 and thesis.get("symbol") == SYMBOL
                                      and thesis.get("status") == "researching"
                                      and thesis.get("conviction") == 1,
            "source_url_in_evidence": bool(data) and text_contains(evidence, data["source_url"]),
            "dates_in_evidence": bool(data) and all(text_contains(evidence, str(item))
                                                    for item in (first.get("date"), latest.get("date"))),
            "closes_in_evidence": bool(data) and all(text_contains(evidence, str(item))
                                                     for item in (first.get("close"), latest.get("close"))),
            "return_arithmetic": (expected_change_pct is not None
                                  and isinstance(evidence_change, (float, int))
                                  and abs(evidence_change - expected_change_pct) <= 0.02),
            "limits_recorded": all(text_contains(thesis, term)
                                   for term in ("earnings", "valuation", "catalysts")),
            "no_alert": not state["alerts"],
            "priced_flash": bool(pilot.turns) and all(turn["priced_usage"] for turn in pilot.turns),
            "within_cost_cap": pilot.cost < CAP_USD,
        }
        result = {
            "status": "mechanical_pass" if not error and all(checks.values()) else "needs_review",
            "error": error, "checks": checks, "model": MODEL,
            "skill_script": str(args.skill_root / "scripts" / "stock_data.py"),
            "skill_script_sha256": sha256(args.skill_root / "scripts" / "stock_data.py"),
            "gateway_binary_sha256": sha256(args.gateway_binary),
            "plugin_sha256": sha256(PLUGIN_PATH),
            "retrieved": data, "expected_first_to_latest_pct": expected_change_pct,
            "tool_calls": tool_names, "estimated_cost_usd": pilot.cost,
            "cost_cap_usd": CAP_USD, "state": state, "turns": pilot.turns,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "boundary": "live Skill price retrieval plus preliminary ledger thesis; no SEC, valuation, trade, or portfolio action",
        }
        args.output_dir.mkdir(parents=True)
        shutil.copy2(pilot.home / "finance-tools.db", args.output_dir / "finance-tools.db")
        output = args.output_dir / "result.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        (args.output_dir / "RESULT-SHA256.txt").write_text(
            hashlib.sha256(output.read_bytes()).hexdigest() + "  result.json\n"
            + hashlib.sha256((args.output_dir / "finance-tools.db").read_bytes()).hexdigest()
            + "  finance-tools.db\n")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--python-exe", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({"status": result["status"], "error": result["error"],
                      "checks": result["checks"], "tool_calls": result["tool_calls"],
                      "estimated_cost_usd": result["estimated_cost_usd"]},
                     ensure_ascii=False), flush=True)
    return 0 if result["status"] == "mechanical_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
