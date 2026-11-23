#!/usr/bin/env python3
"""Free HTTP Gateway replay of malformed finance tool JSON and bounded repair."""

import argparse
import json
import tempfile
from pathlib import Path

import run_finance_gateway_fault_replay as prior
from run_thesis_event_panel import ROOT, sha256


def raw_tool_stream(call_id, name, arguments):
    payload = {"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": call_id, "type": "function",
        "function": {"name": name, "arguments": arguments},
    }]}}]}
    return f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()


def run_case(case_id, template_db, binary, temp_root):
    pilot = prior.base.Pilot(case_id, template_db, binary, temp_root, False, 0.0)
    thesis, alert = prior.seed(pilot)
    valid = {"thesis_id": thesis["id"], "alert_id": alert["id"],
             "expected_version": thesis["version"],
             "event": {"summary": alert["event"]["summary"]},
             "impact": "neutral", "decision": "maintain",
             "rationale": "Local synthetic fixture reports revenue of 100 USD million."}
    malformed = json.dumps(valid) + "}"
    if case_id == "repair":
        responses = [
            raw_tool_stream("bad-1", "finance-tools__thesis_record_review", malformed),
            prior.tool_stream("good-1", "finance-tools__thesis_record_review", valid),
            prior.tool_stream("ack-1", "finance-tools__alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"]}),
            prior.text_stream("Local fixture workflow complete."),
        ]
    else:
        responses = [
            raw_tool_stream("bad-1", "finance-tools__thesis_record_review", malformed),
            raw_tool_stream("bad-2", "finance-tools__thesis_record_review", malformed),
        ]
    with prior.ScriptedProvider(responses) as scripted:
        prior.configure_provider(pilot.home, scripted.url)
        process, log = prior.base.start_gateway(pilot.home)
        try:
            response = prior.gateway_turn(pilot, case_id)
        finally:
            prior.base.stop_gateway(process, log)
        provider_requests = scripted.received
        unused = len(scripted.responses)
    state = pilot.ledger_state()
    trace = response.get("fastclaw", {}).get("trace", [])
    calls = [event for event in trace if event.get("type") == "tool_call"]
    results = [event for event in trace if event.get("type") == "tool_result"]
    terminals = [event.get("code") for event in trace if event.get("type") == "terminal"]
    trace_errors = [event.get("message") for event in trace if event.get("type") == "error"]
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    reviews = state["theses"][0]["reviews"]
    alert_status = state["alerts"][0]["status"]
    checks = {
        "local_provider_only": provider_requests == len(responses) and unused == 0,
        "tool_results_paired": len(calls) == len(results) and
                               {event["id"] for event in calls} == {event["id"] for event in results},
        "invalid_arguments_rejected": sum(
            "invalid tool arguments JSON" in (event.get("result") or "")
            for event in results) == (1 if case_id == "repair" else 2),
        "no_trace_error": not trace_errors,
        "state_and_terminal": (
            len(reviews) == 1 and alert_status == "acknowledged" and
            final == "Local fixture workflow complete." and not terminals
            if case_id == "repair" else
            len(reviews) == 0 and alert_status == "new" and
            terminals == ["malformed_tool_arguments_exhausted"]
        ),
    }
    return {"case_id": case_id, "checks": checks, "provider_requests": provider_requests,
            "tool_calls": len(calls), "tool_results": len(results),
            "terminal_codes": terminals, "trace_errors": trace_errors,
            "review_count": len(reviews), "alert_status": alert_status,
            "final_text": final}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB or Gateway binary")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), Path(prior.__file__), Path(prior.base.__file__), prior.PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_no_external_api")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="finance-json-replay-v2-") as temp_root:
        for case_id in ("repair", "exhausted"):
            result = run_case(case_id, args.template_db, args.gateway_binary, temp_root)
            (args.output_dir / f"{case_id}.json").write_text(json.dumps(result, indent=2) + "\n")
            print(json.dumps(result), flush=True)
            if not all(result["checks"].values()):
                raise AssertionError(f"{case_id} Gateway replay failed")


if __name__ == "__main__":
    main()
