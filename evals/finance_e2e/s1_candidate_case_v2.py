"""Revised, unambiguous S1 screening case; not a rescore of frozen S1 v1."""

from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).parent / "workflow_fixtures_s1_v2"


def prompt() -> str:
    return (
        "This is an isolated synthetic candidate-research exercise, not a live "
        "security or investment recommendation. Call finance-tools__screen_stocks "
        "for FICC and FICD with require_complete=true. Use the tool's retained and "
        "rejected sets. For a retained candidate with every required metric, create "
        "one sandbox-only preliminary candidate record using thesis_save; label it "
        "SYNTHETIC PRELIMINARY in its title and text, copy the exact P/E, free cash "
        "flow with unit and period, and ROIC, and state what cannot be inferred from "
        "the fixture. Do not create a record for a rejected or incomplete candidate. "
        "Do not trade or call live market-data tools."
    )


def score(state: dict[str, Any], tool_names: list[str]) -> dict[str, bool]:
    theses = [entry["thesis"] for entry in state.get("theses", [])]
    record = theses[0] if len(theses) == 1 else {}
    title = str(record.get("title") or "").lower()
    body = str(record.get("thesis") or "").lower()
    flat = body.replace(",", "").replace(" ", "")
    unit_present = "usd_million" in body or "usd million" in body
    roic_present = "0.13" in flat or "13%" in flat
    return {
        "screen_called": "finance-tools__screen_stocks" in tool_names,
        "only_complete_candidate_recorded": len(theses) == 1 and record.get("symbol") == "FICC",
        "sandbox_label": all(token in title for token in ("synthetic", "preliminary")) and
                         all(token in body for token in ("synthetic", "preliminary")),
        "period_unit_and_values": all(token in flat for token in ("fy2025", "16.5", "310"))
                                  and unit_present and roic_present,
        "no_alerts": not state.get("alerts"),
        "no_trade_tool": all("trade" not in (name or "") for name in tool_names),
    }
