#!/usr/bin/env python3
"""Replay finance tool errors through an isolated Gateway and local scripted provider."""

import argparse
import json
import sqlite3
import tempfile
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import AGENT_ID, HERE, PLUGIN_PATH, ROOT, sha256


def tool_stream(call_id, name, arguments):
    payload = {"choices": [{"delta": {"tool_calls": [{
        "index": 0, "id": call_id, "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }]}}]}
    return f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()


def text_stream(content):
    payload = {"choices": [{"delta": {"content": content}}]}
    return f"data: {json.dumps(payload)}\n\ndata: [DONE]\n\n".encode()


class ScriptedProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.received = 0
        self.requests = []

        provider = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(size)
                provider.received += 1
                provider.requests.append(json.loads(body))
                if self.path != "/chat/completions" or not provider.responses:
                    self.send_error(500, "unexpected scripted provider request")
                    return
                payload = provider.responses.pop(0)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()


def configure_provider(home, local_url):
    with sqlite3.connect(home / "fastclaw.db") as database:
        row = database.execute(
            "SELECT id FROM configs WHERE kind='provider' AND scope='system' AND name='deepseek'"
        ).fetchone()
        if row is None:
            raise ValueError("isolated template lacks DeepSeek provider slot")
        # Replace the copied provider settings before the Gateway starts. No
        # real credential or provider URL is retained in this replay home.
        fixture = {"apiBase": local_url, "apiKey": "local-fixture-only",
                   "apiType": "openai-chat", "authType": "bearer-token",
                   "models": [{"id": "deepseek-v4-pro", "name": "local scripted fixture"}]}
        database.execute("UPDATE configs SET data=? WHERE id=?",
                         (json.dumps(fixture), row[0]))


def seed(pilot):
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "FICE", "thesis": "Local fixture research thesis.",
        "status": "active", "conviction": 3,
        "required_event_metrics": ["quarterly_revenue"],
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FICE", "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": ["FICE"], "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": "FICE", "event": {
            "type": "earnings", "summary": "FICE fixture quarterly revenue 100.",
            "sources": [{"id": "fixture", "sha256": "a" * 64}],
            "observed_metrics": {"quarterly_revenue": {
                "value": "100", "unit": "USD_million", "fact_id": "FICE-REV"}},
        },
    }, pilot.tenant)["results"][0]["alert"]
    return thesis, alert


def gateway_turn(pilot, case_id):
    request = urllib.request.Request(
        "http://127.0.0.1:18955/v1/chat/completions",
        data=json.dumps({"messages": [{"role": "user", "content": "Fixed local fault replay."}],
                         "stream": False,
                         "fastclaw": {"eval": True, "include_trace": True,
                                      "include_usage_breakdown": True,
                                      "server_timeout_ms": 120000}}).encode(),
        headers={"Authorization": "Bearer " + pilot.token,
                 "Content-Type": "application/json",
                 "x-fastclaw-agent-id": AGENT_ID,
                 "x-fastclaw-session-key": "finance-fault-" + case_id},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=130) as handle:
        return json.load(handle)


def run_case(case_id, template_db, binary, temp_root):
    pilot = base.Pilot(case_id, template_db, binary, temp_root, False, 0.0)
    thesis, alert = seed(pilot)
    valid = {"thesis_id": thesis["id"], "alert_id": alert["id"],
             "expected_version": thesis["version"],
             "event": {"summary": alert["event"]["summary"]},
             "impact": "neutral", "decision": "maintain",
             "rationale": "The local fixture reports revenue of 100 USD million."}
    bad = {key: value for key, value in valid.items() if key != "thesis_id"}
    if case_id == "recovery":
        responses = [
            tool_stream("bad-1", "finance-tools__thesis_record_review", bad),
            tool_stream("good-1", "finance-tools__thesis_record_review", valid),
            tool_stream("ack-1", "finance-tools__alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"]}),
            text_stream("Local fixture workflow complete."),
        ]
    else:
        responses = [
            tool_stream(f"bad-{index}", "finance-tools__thesis_record_review",
                        {**bad, "rationale": f"Malformed fixture attempt {index}."})
            for index in range(1, 9)
        ]
    with ScriptedProvider(responses) as scripted:
        configure_provider(pilot.home, scripted.url)
        process, log = base.start_gateway(pilot.home)
        try:
            response = gateway_turn(pilot, case_id)
        finally:
            base.stop_gateway(process, log)
        provider_calls = scripted.received
        unused_responses = len(scripted.responses)
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    alerts = state["alerts"]
    trace = response.get("fastclaw", {}).get("trace", [])
    calls = [item for item in trace if item.get("type") == "tool_call"]
    results = [item for item in trace if item.get("type") == "tool_result"]
    error_codes = []
    for item in results:
        try:
            payload = json.loads(item.get("result") or "{}")
        except json.JSONDecodeError:
            continue
        error_codes.extend(error.get("code") for error in payload.get("errors", []))
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    checks = {
        "provider_local_only": provider_calls == (4 if case_id == "recovery" else 8)
                               and unused_responses == 0,
        "tool_results_paired": len(calls) == len(results)
                               and {item["id"] for item in calls} == {item["id"] for item in results},
        "malformed_calls_rejected": error_codes.count("invalid_input") ==
                                    (1 if case_id == "recovery" else 8),
        "state_matches_branch": (
            len(reviews) == 1 and alerts[0]["status"] == "acknowledged"
            if case_id == "recovery" else
            len(reviews) == 0 and alerts[0]["status"] == "new"
        ),
        "terminal_matches_branch": (
            final == "Local fixture workflow complete."
            if case_id == "recovery" else
            "maximum number of tool iterations" in final.lower()
        ),
    }
    return {"case_id": case_id, "checks": checks, "error_codes": error_codes,
            "provider_requests": provider_calls, "tool_calls": len(calls),
            "tool_results": len(results), "final_text": final,
            "review_count": len(reviews), "alert_status": alerts[0]["status"]}


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
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in
                (Path(__file__), HERE / "run_finance_workflow_pilot.py",
                 HERE / "run_thesis_event_panel.py", PLUGIN_PATH)}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_no_external_api")
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="finance-gateway-fault-replay-") as temp_root:
        for case_id in ("recovery", "budget"):
            result = run_case(case_id, args.template_db, args.gateway_binary, temp_root)
            (args.output_dir / f"{case_id}.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            if not all(result["checks"].values()):
                raise AssertionError(f"{case_id} deterministic replay failed")


if __name__ == "__main__":
    main()
