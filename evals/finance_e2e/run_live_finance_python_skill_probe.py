#!/usr/bin/env python3
"""Two read-only FinData Skill probes through the existing Python Gateway.

The probe creates an agent-scoped API key in the Python Gateway database and
revokes it before exiting. It does not edit plugin, Skill, or Gateway config.
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
    ("us_amd_nasdaq_history", "agt_4e85c80c71dc538a1139", "findata-toolkit-us",
     ["scripts/stock_data.py", "AMD", "--history", "--period", "5d",
      "--source", "nasdaq"]),
    ("cn_600519_sina_history", "agt_1dc684cc47fb854b005b", "findata-toolkit-cn",
     ["scripts/stock_data.py", "600519", "--history", "--period", "30d",
      "--source", "sina"]),
)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def interrupt(_signal_number: int, _frame: object) -> None:
    raise KeyboardInterrupt("probe interrupted; revoking temporary API key")


def request_json(url: str, token: str, payload: dict, timeout: int = 10) -> dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def run_case(base_url: str, token: str, case: tuple) -> dict:
    case_id, agent_id, skill, argv = case
    session_id = "finance-python-skill-probe-" + case_id + "-" + secrets.token_hex(6)
    message = (
        "Read-only online data retrieval check. Use the prepared FinData Toolkit "
        "Skill, not arbitrary shell commands and not a finance-tools plugin. "
        "Make exactly one native exec tool call with these JSON arguments: "
        + json.dumps({"skill": skill, "argv": argv}, ensure_ascii=False)
        + ". Do not call other tools or modify any ledger, thesis, alert, or portfolio. "
        "After the call, report whether it returned valid dated data or the exact error. "
        "For valid history, distinguish the lookback period from the bar interval, "
        "preserve the declared units, and label prices[0].close as the first close "
        "and prices[-1].close as the latest close. Do not infer extra units, "
        "data-source behavior, or quality claims not proven by the tool output."
    )
    request = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat/stream",
        data=json.dumps({"agentId": agent_id, "sessionId": session_id, "message": message}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                 "Accept": "text/event-stream"},
        method="POST",
    )
    result = {"case_id": case_id, "agent_id": agent_id, "skill": skill, "argv": argv,
              "session_id": session_id, "started_at_utc": now(), "events": []}
    try:
        with urllib.request.urlopen(request, timeout=240) as response:
            result["http_status"] = response.status
            for line in response:
                if line.startswith(b"data: "):
                    result["events"].append(json.loads(line[6:]))
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["error"] = exc.read(4096).decode(errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        try:
            result["stop"] = request_json(
                base_url.rstrip("/") + "/api/chat/stop", token,
                {"agentId": agent_id, "sessionId": session_id},
            )
        except Exception as stop_exc:
            result["stop_error"] = str(stop_exc)
    result["finished_at_utc"] = now()
    return result


def dated_history_result(events: list[dict]) -> dict | None:
    for event in events:
        if event.get("type") != "tool_result":
            continue
        data = event.get("data", {})
        if data.get("name") != "exec" or data.get("isError") is True:
            continue
        try:
            result = json.loads(data.get("result", ""))
        except (TypeError, ValueError):
            continue
        if (
            isinstance(result, dict)
            and not result.get("error")
            and result.get("source_url")
            and result.get("start_date")
            and result.get("end_date")
            and isinstance(result.get("prices"), list)
            and result["prices"]
        ):
            return result
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18954")
    parser.add_argument("--case-id", action="append", choices=[case[0] for case in CASES],
                        help="Run only a named case; may be specified more than once")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; refusing to overwrite")
    signal.signal(signal.SIGINT, interrupt)
    signal.signal(signal.SIGTERM, interrupt)

    token = "fc_" + secrets.token_urlsafe(32)
    key_id = "key_finance_python_skill_probe_" + secrets.token_hex(8)
    record = {"gateway": args.base_url, "key_revoked": False, "cases": []}
    selected_cases = tuple(
        case for case in CASES if not args.case_id or case[0] in args.case_id
    )
    agent_ids = tuple(dict.fromkeys(case[1] for case in selected_cases))
    with sqlite3.connect(args.database, timeout=15) as db:
        agents = db.execute(
            f"SELECT id,user_id FROM agents WHERE id IN ({','.join('?' for _ in agent_ids)})",
            agent_ids,
        ).fetchall()
        if len(agents) != len(agent_ids) or len({user_id for _, user_id in agents}) != 1:
            raise RuntimeError("expected selected agents to belong to the same user")
        db.execute(
            "INSERT INTO apikeys(id,user_id,name,key_hash,key_prefix,type,created_at) "
            "VALUES (?,?,?,?,?,'agent',CURRENT_TIMESTAMP)",
            (key_id, agents[0][1], "temporary-finance-python-skill-probe",
             hashlib.sha256(token.encode()).hexdigest(), token[:12]),
        )
        db.executemany(
            "INSERT INTO apikey_agents(apikey_id,agent_id) VALUES (?,?)",
            [(key_id, agent_id) for agent_id in agent_ids],
        )
        db.commit()
        try:
            for case in selected_cases:
                result = run_case(args.base_url, token, case)
                record["cases"].append(result)
                names = [ev.get("data", {}).get("name") for ev in result["events"]
                         if ev.get("type") == "tool_call"]
                tool_errors = [ev.get("data", {}).get("result") for ev in result["events"]
                               if ev.get("type") == "tool_result"
                               and ev.get("data", {}).get("isError") is True]
                history = dated_history_result(result["events"])
                print(json.dumps({"case_id": case[0], "http_status": result.get("http_status"),
                                  "tool_calls": names, "tool_errors": tool_errors,
                                  "data_points": history.get("data_points") if history else None,
                                  "error": result.get("error")},
                                 ensure_ascii=False), flush=True)
        finally:
            db.execute("DELETE FROM apikey_agents WHERE apikey_id=?", (key_id,))
            db.execute("DELETE FROM apikeys WHERE id=?", (key_id,))
            db.commit()
            record["key_revoked"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if all(
        case.get("http_status") == 200
        and dated_history_result(case["events"]) is not None
        and not any(ev.get("type") == "error" for ev in case["events"])
        for case in record["cases"]
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
