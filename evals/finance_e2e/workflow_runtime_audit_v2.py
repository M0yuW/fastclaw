"""Fail-closed runtime checks for new finance workflow observations.

This module reads observations; it never changes frozen results or scores.
"""

from collections import Counter
from typing import Any


def audit_turns(turns: list[dict[str, Any]]) -> dict[str, Any]:
    call_ids: list[str] = []
    result_ids: list[str] = []
    trace_errors: list[str] = []
    terminal_codes: list[str] = []
    uncertain_calls: list[int] = []
    unpriced_calls: list[int] = []
    request_errors: list[str] = []
    model_count = 0
    for turn in turns:
        if turn.get("error"):
            request_errors.append(str(turn["error"]))
        response = turn.get("response") or {}
        metadata = response.get("fastclaw") or {}
        for event in metadata.get("trace") or []:
            if event.get("type") == "tool_call":
                call_ids.append(str(event.get("id") or ""))
            elif event.get("type") == "tool_result":
                result_ids.append(str(event.get("id") or ""))
            elif event.get("type") == "error":
                trace_errors.append(str(event.get("message") or "unknown trace error"))
            elif event.get("type") == "terminal":
                terminal_codes.append(str(event.get("code") or "unknown terminal"))
        for model_call in metadata.get("model_calls") or []:
            model_count += 1
            if model_call.get("cost_uncertain"):
                uncertain_calls.append(model_count)
            if model_call.get("priced") is not True:
                unpriced_calls.append(model_count)
        final_text = ((response.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        if "maximum number of tool iterations" in final_text.lower() and not terminal_codes:
            terminal_codes.append("legacy_tool_iteration_budget_exhausted")
    # An abstention can legitimately make zero tool calls; whether a specific
    # workflow required a tool is a case oracle, not a runtime pairing rule.
    paired = Counter(call_ids) == Counter(result_ids)
    return {
        "model_calls": model_count,
        "tool_calls_paired": paired,
        "trace_errors": trace_errors,
        "terminal_codes": terminal_codes,
        "cost_uncertain_sequences": uncertain_calls,
        "unpriced_sequences": unpriced_calls,
        "request_errors": request_errors,
        "clean_completion": bool(turns) and model_count > 0 and paired
                            and not (trace_errors or terminal_codes or uncertain_calls
                                     or unpriced_calls or request_errors),
    }
