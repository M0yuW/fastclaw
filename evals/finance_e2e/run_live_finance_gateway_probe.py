#!/usr/bin/env python3
"""Probe the existing Gateway's finance tool through two read-only agent turns.

Creates an agent-scoped API key only for this process and revokes it in finally.
Does not change Gateway/plugin configuration or invoke a Python finance script
directly. The Gateway itself decides which interpreter runs its plugin scripts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import signal
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


CASES = (
    ("us_amd_history", "agt_4e85c80c71dc538a1139", "US", "AMD", "history", "5d"),
    ("cn_600519_basic", "agt_1dc684cc47fb854b005b", "CN", "600519", "basic", "1y"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def interrupt(_signal_number: int, _frame: object) -> None:
    raise KeyboardInterrupt("probe interrupted; revoking temporary API key")


def call_gateway(base_url: str, token: str, case: tuple[str, ...]) -> dict:
    case_id, agent_id, market, symbol, view, period = case
    message = (
        "Read-only connectivity test. Call finance-tools__stock_snapshot exactly once "
        f'with market="{market}", symbols=["{symbol}"], view="{view}", '
        f'period="{period}". Do not call exec, other tools, or modify any '
        "research ledger, alert, or portfolio. Report whether the tool returned "
        "ok=true and quote its error code if not. Do not invent market data."
    )
    body = json.dumps({
        "agentId": agent_id,
        "sessionId": f"finance-live-probe-{case_id}-{secrets.token_hex(6)}",
        "message": message,
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat/stream",
        data=body,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        },
        method="POST",
    )
    result = {"case_id": case_id, "agent_id": agent_id, "started_at_utc": utc_now(), "events": []}
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result["http_status"] = response.status
            result["content_type"] = response.headers.get("Content-Type")
            for line in response:
                if line.startswith(b"data: "):
                    result["events"].append(json.loads(line[6:]))
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = exc.read(4096).decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
    result["finished_at_utc"] = utc_now()
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18953")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; refusing to overwrite")

    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)
    token = "fc_" + secrets.token_hex(32)
    key_id = "k_finance_live_probe_" + secrets.token_hex(8)
    record = {"gateway": args.base_url, "key_revoked": False, "cases": []}
    with sqlite3.connect(args.database, timeout=15) as db:
        agents = db.execute(
            "SELECT id,user_id FROM agents WHERE id IN (?,?)",
            (CASES[0][1], CASES[1][1]),
        ).fetchall()
        if len(agents) != 2 or len({user_id for _, user_id in agents}) != 1:
            raise RuntimeError("expected two existing agents belonging to the same user")
        db.execute(
            "INSERT INTO apikeys(id,user_id,name,key_hash,key_prefix) VALUES (?,?,?,?,?)",
            (key_id, agents[0][1], "temporary-finance-live-probe", hashlib.sha256(token.encode()).hexdigest(), token[:10]),
        )
        db.executemany(
            "INSERT INTO apikey_agents(apikey_id,agent_id) VALUES (?,?)",
            [(key_id, agent_id) for agent_id, _ in agents],
        )
        db.commit()
        try:
            for case in CASES:
                result = call_gateway(args.base_url, token, case)
                record["cases"].append(result)
                names = [ev.get("data", {}).get("name") for ev in result["events"] if ev.get("type") == "tool_call"]
                print(json.dumps({"case_id": case[0], "http_status": result.get("http_status"),
                                  "tool_calls": names, "error": result.get("error")}, ensure_ascii=False), flush=True)
        finally:
            db.execute("DELETE FROM apikey_agents WHERE apikey_id=?", (key_id,))
            db.execute("DELETE FROM apikeys WHERE id=?", (key_id,))
            db.commit()
            record["key_revoked"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(
        case.get("http_status") == 200 and any(
            ev.get("type") == "tool_result" and
            ev.get("data", {}).get("name") == "finance-tools__stock_snapshot"
            for ev in case["events"]
        ) for case in record["cases"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
