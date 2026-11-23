"""Offline, model-free attribution of finance workflow tool failures."""

import json
from collections import Counter
from typing import Any


def audit_attempt(attempt: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
    schemas = {item["name"]: item for item in definitions}
    calls: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for turn_index, turn in enumerate(attempt.get("turns", []), start=1):
        trace = ((turn.get("response") or {}).get("fastclaw") or {}).get("trace") or []
        for event in trace:
            if event.get("type") == "tool_call":
                name = str(event.get("name") or "")
                local_name = name.split("__", 1)[-1]
                schema = schemas.get(local_name, {})
                try:
                    arguments = json.loads(event.get("arguments") or "{}")
                except json.JSONDecodeError:
                    arguments = None
                required = (schema.get("parameters") or {}).get("required") or []
                missing = sorted(
                    field for field in required
                    if not isinstance(arguments, dict) or field not in arguments
                )
                call = {"id": event.get("id"), "turn": turn_index,
                        "round": event.get("round"), "tool": local_name,
                        "missing_required": missing, "ok": None, "error_codes": []}
                calls.append(call)
                by_id[call["id"]] = call
            elif event.get("type") == "tool_result":
                call = by_id.get(event.get("id"))
                if call is None:
                    continue
                try:
                    payload = json.loads(event.get("result") or "{}")
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    call["ok"] = payload.get("ok")
                    call["error_codes"] = [
                        item.get("code") for item in payload.get("errors", [])
                        if isinstance(item, dict) and item.get("code")
                    ]
    terminal_text = "\n".join(
        ((turn.get("response") or {}).get("choices") or [{}])[0]
        .get("message", {}).get("content", "") or ""
        for turn in attempt.get("turns", [])
    )
    budget_exhausted = "maximum number of tool iterations" in terminal_text.lower()
    missing_calls = [call for call in calls if call["missing_required"]]
    rejected_calls = [call for call in calls if call["ok"] is False]
    recovered_calls = [call for call in calls if call["ok"] is True and
                       any(previous["tool"] == call["tool"] and
                           previous["ok"] is False and
                           calls.index(previous) < calls.index(call)
                           for previous in calls)]
    checks = attempt.get("checks") or {}
    return {
        "attempt_id": attempt.get("run_id"),
        "missing_required_calls": missing_calls,
        "rejected_tool_calls": rejected_calls,
        "error_codes": dict(Counter(code for call in rejected_calls
                                    for code in call["error_codes"])),
        "later_successful_retry": bool(recovered_calls),
        "budget_exhausted": budget_exhausted,
        "request_error": any(turn.get("error") for turn in attempt.get("turns", [])),
        "workflow_complete": bool(checks) and all(checks.values()) and not budget_exhausted,
        "tool_call_count": len(calls),
        "unpaired_calls": [call["id"] for call in calls if call["ok"] is None],
    }
