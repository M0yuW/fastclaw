#!/usr/bin/env python3
"""Run a bounded four-case SEC event-to-thesis panel against isolated Gateways.

Each case gets a fresh copy of the Gateway configuration DB, an empty finance
ledger, and a new session. Results are append-only; this runner never resumes
or overwrites an output directory. The old Stage 2/smoke artifacts are inputs
only. Pricing is an estimate, not a provider invoice.
"""

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from run_thesis_event_gateway import create_ephemeral_key, load_plugin, must_call
from test_thesis_event_integration import HERE, ROOT, PLUGIN_PATH, locked_episode

SUITE = HERE / "thesis_event_panel_v1.json"
AGENT_ID = "finance-coordinator"
PORT = 18955


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_ref(source):
    return {key: source[key] for key in ("id", "url", "sha256")}


def metric_text(episode, ids):
    facts = {item["id"]: item for item in episode["facts"]}
    rendered = []
    for fact_id in ids:
        fact = facts[fact_id]
        unit = {"USD_million": "USD million", "percent": "%", "basis_point": "basis points"}[fact["unit"]]
        rendered.append(f"{fact_id}={fact['value']} {unit}")
    return "; ".join(rendered)


def validate_suite(suite):
    assert suite["suite_id"] == "thesis-event-panel-v1"
    assert len(suite["cases"]) == 4
    assert len({case["id"] for case in suite["cases"]}) == 4
    for case in suite["cases"]:
        before, _ = locked_episode(case["baseline_episode"])
        after, _ = locked_episode(case["event_episode"])
        assert before["symbol"] == after["symbol"] == case["symbol"]
        for episode, ids in ((before, case["baseline_metrics"]), (after, case["event_metrics"])):
            fact_ids = {item["id"] for item in episode["facts"]}
            assert ids and set(ids) <= fact_ids
        assert not set(case["event_metrics"]) & set(case["baseline_metrics"])
        assert not any(word in case["seed_thesis"].lower() for word in ("conviction 3", "decision=", "choose maintain"))


def prepare_home(template_db, binary, temporary_root):
    home = Path(tempfile.mkdtemp(prefix="case-", dir=temporary_root))
    with sqlite3.connect(f"file:{template_db}?mode=ro", uri=True) as source:
        with sqlite3.connect(home / "fastclaw.db") as dest:
            source.backup(dest)
    with sqlite3.connect(home / "fastclaw.db") as conn:
        row = conn.execute(
            "SELECT id,data FROM configs WHERE kind='setting' AND scope='system' AND name='plugins'"
        ).fetchone()
        if not row:
            raise ValueError("template has no plugin settings")
        settings = json.loads(row[1])
        settings["paths"] = [str(ROOT / "plugins")]
        entries = settings["entries"]
        for name, entry in entries.items():
            entry["enabled"] = name == "finance-tools"
        entries["finance-tools"].setdefault("config", {})["stateDbPath"] = str(home / "finance-tools.db")
        entries["finance-tools"]["config"]["finskillsPath"] = str(ROOT)
        conn.execute("UPDATE configs SET data=? WHERE id=?", (json.dumps(settings), row[0]))
        row = conn.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
        if not row:
            raise ValueError("template lacks finance coordinator")
        agent = json.loads(row[0])
        agent.update(policy="finance-review-only", maxToolIterations=6, maxTokens=2048)
        conn.execute("UPDATE agents SET config=? WHERE id=?", (json.dumps(agent), AGENT_ID))
        # Remove ephemeral keys from an older isolated smoke snapshot, never
        # from the source DB. The newly created key is case-specific.
        old_keys = [row[0] for row in conn.execute("SELECT id FROM apikeys WHERE name='finance-event-one-attempt'")]
        for key_id in old_keys:
            conn.execute("DELETE FROM apikey_agents WHERE apikey_id=?", (key_id,))
            conn.execute("DELETE FROM apikeys WHERE id=?", (key_id,))
    shutil.copy2(binary, home / "fastclaw")
    return home


def gateway_ready():
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            return True
    except OSError:
        return False


def start_gateway(home):
    if gateway_ready():
        raise RuntimeError(f"port {PORT} already occupied; do not touch the existing Gateway")
    log = (home / "gateway.log").open("wb")
    env = dict(os.environ, FASTCLAW_HOME=str(home))
    process = subprocess.Popen([str(home / "fastclaw"), "gateway", "--port", str(PORT)],
                               env=env, stdout=log, stderr=subprocess.STDOUT)
    # The HTTP listener starts before Gateway.Run finishes plugin initialization.
    # Port readiness alone can race finance-tool registration and yield a model
    # turn with no available tools. Wait for the gateway's post-plugin marker.
    for _ in range(300):
        if process.poll() is not None:
            log.close()
            raise RuntimeError(f"Gateway exited with code {process.returncode}")
        started = (home / "gateway.log").read_text(errors="replace")
        if gateway_ready() and 'msg="gateway started"' in started:
            return process, log
        time.sleep(0.1)
    process.terminate()
    process.wait(timeout=5)
    log.close()
    raise RuntimeError("Gateway did not finish startup in 30 seconds")


def stop_gateway(process, log):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log.close()
    for _ in range(30):
        if not gateway_ready():
            break
        time.sleep(0.1)


def prompt_for(case, thesis_id, alert_id):
    return (
        "Perform a bounded SEC-event research-thesis review, not investment advice. "
        "Use finance-tools__thesis_get and finance-tools__alert_list to read the current thesis "
        "and the newly ingested alert. Evaluate the baseline and event figures, compute relevant "
        "changes with correct periods and units, identify supporting evidence, risks, and any "
        "missing information. The event packet is a subset of a source-locked SEC document; "
        "do not claim that a field missing from the packet is absent from the filing itself. "
        "Choose the impact, decision, status, and conviction yourself, explaining any change. "
        "Call finance-tools__thesis_record_review exactly once with the observed version and "
        "event source ID/hash, then acknowledge the alert using finance-tools__alert_update "
        "with its observed version. Do not trade or alter a portfolio. "
        f"Case {case['id']}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


def execute_case(case, suite, template_db, binary, temporary_root):
    home = prepare_home(template_db, binary, temporary_root)
    baseline, baseline_source = locked_episode(case["baseline_episode"])
    episode, event_source = locked_episode(case["event_episode"])
    token, user_id = create_ephemeral_key(home / "fastclaw.db", AGENT_ID)
    tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "fixture-seed"}
    finance = load_plugin().FinanceToolsPlugin()
    finance.initialize({"stateDbPath": str(home / "finance-tools.db")})
    assert must_call(finance, "thesis_list", {}, tenant)["count"] == 0
    thesis = must_call(finance, "thesis_save", {
        "market": "US", "symbol": case["symbol"], "title": f"{case['symbol']} filing review thesis",
        "thesis": f"{case['baseline_label']} SEC baseline: "
                  f"{metric_text(baseline, case['baseline_metrics'])}. {case['seed_thesis']}",
        "status": "active", "conviction": 3, "catalysts": case["seed_catalysts"],
        "invalidations": case["seed_invalidations"], "evidence": [source_ref(baseline_source)],
    }, tenant)["thesis"]
    must_call(finance, "watchlist_save", {
        "market": "US", "symbol": case["symbol"], "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [case["symbol"]], "min_match_score": 1,
    }, tenant)
    event = {
        "external_id": episode["source_id"], "type": "earnings", "as_of": episode["observed_at"],
        "summary": f"{case['symbol']} {case['event_label']} SEC event packet: "
                   f"{metric_text(episode, case['event_metrics'])}.",
        "sources": [source_ref(event_source)],
    }
    ingested = must_call(finance, "event_alert_ingest", {
        "market": "US", "symbol": case["symbol"], "event": event,
    }, tenant)
    assert ingested["created"] == 1
    alert = ingested["results"][0]["alert"]
    prompt = prompt_for(case, thesis["id"], alert["id"])
    assert "oracle" not in prompt and "conviction 3" not in prompt.lower()
    request_body = {
        "messages": [{"role": "user", "content": prompt}], "stream": False,
        "fastclaw": {"eval": True, "include_trace": True, "include_usage_breakdown": True,
                     "server_timeout_ms": 120000,
                     "pricing": suite["pricing_usd_per_million_tokens"]},
    }
    process, log = start_gateway(home)
    response, error = None, None
    started = time.monotonic()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions",
            data=json.dumps(request_body).encode(),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json",
                     "x-fastclaw-agent-id": AGENT_ID,
                     "x-fastclaw-session-key": "finance-panel-" + case["id"]}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=150) as handle:
                response = json.load(handle)
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read(2048).decode(errors='replace')}"
        except (urllib.error.URLError, TimeoutError) as exc:
            error = str(exc)
    finally:
        elapsed = time.monotonic() - started
        stop_gateway(process, log)
    fetched = must_call(finance, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
    reviews, actual = fetched["reviews"], fetched["thesis"]
    alerts = must_call(finance, "alert_list", {"symbol": case["symbol"]}, tenant)["alerts"]
    model_calls = (response or {}).get("fastclaw", {}).get("model_calls", [])
    estimated_cost = sum(call.get("estimated_cost_usd", 0) for call in model_calls)
    priced = bool(model_calls) and all(call.get("priced") is True for call in model_calls)
    review = reviews[0] if len(reviews) == 1 else None
    decision = review.get("decision") if review else None
    checks = {
        "one_review": len(reviews) == 1,
        "version_once": actual["version"] == thesis["version"] + 1,
        "source_recorded": bool(review) and any(
            source.get("id") == event_source["id"] and source.get("sha256") == event_source["sha256"]
            for source in review["event"].get("sources", [])),
        "alert_acknowledged": len(alerts) == 1 and alerts[0]["status"] == "acknowledged",
        "priced_usage": priced,
        "decision_in_predeclared_set": decision in case["oracle"]["acceptable_decisions"],
        "status_in_predeclared_set": actual["status"] in case["oracle"]["status_constraint"],
    }
    result = {
        "case_id": case["id"], "scenario": case["scenario"],
        "status": "workflow_pass" if error is None and all(checks.values()) else "needs_review",
        "error": error, "elapsed_seconds": round(elapsed, 3), "checks": checks,
        "seed": {"baseline_episode": case["baseline_episode"], "event_episode": case["event_episode"],
                 "baseline_source": source_ref(baseline_source), "event_source": source_ref(event_source),
                 "event_packet_metric_ids": case["event_metrics"], "thesis_version": thesis["version"],
                 "thesis_status": thesis["status"], "thesis_conviction": thesis["conviction"]},
        "after": {"version": actual["version"], "status": actual["status"],
                  "conviction": actual["conviction"], "reviews": len(reviews),
                  "alert_statuses": [item["status"] for item in alerts]},
        "review": review, "estimated_cost_usd": estimated_cost, "model_calls": len(model_calls),
        "prompt": prompt, "event_packet": event,
        "gateway_response": response,
        "manual_rubric_pending": ["source facts", "arithmetic", "risk recognition", "decision coherence"],
    }
    return result, home


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    suite = json.loads(SUITE.read_text(encoding="utf-8"))
    validate_suite(suite)
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("isolated Gateway template and binary are required")
    args.output_dir.mkdir(parents=True)
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in (
        SUITE, HERE / "evidence.json", HERE / "source-lock.json", PLUGIN_PATH,
        ROOT / "internal/policy/defaults.go", ROOT / "internal/plugin/tool_adapter.go", Path(__file__))}
    manifest["gateway_binary_sha256"] = sha256(args.gateway_binary)
    manifest["gateway_template_db_sha256"] = sha256(args.template_db)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    total = 0.0
    with tempfile.TemporaryDirectory(prefix="thesis-panel-") as temporary_root:
        for case in suite["cases"]:
            result, home = execute_case(case, suite, args.template_db, args.gateway_binary, temporary_root)
            case_dir = args.output_dir / case["id"]
            case_dir.mkdir()
            (case_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            # Keep the isolated ledger as a read-only audit artifact; it is not a personal ledger.
            shutil.copy2(home / "finance-tools.db", case_dir / "finance-tools.db")
            total += result["estimated_cost_usd"]
            print(json.dumps({"case_id": case["id"], "status": result["status"],
                              "error": result["error"], "checks": result["checks"],
                              "estimated_cost_usd": result["estimated_cost_usd"]}, ensure_ascii=False), flush=True)
            if not result["checks"]["priced_usage"] or result["error"] or total >= suite["estimated_spend_stop_usd"]:
                print("STOP: pricing uncertain, request error, or estimated budget reached", flush=True)
                break
    print(json.dumps({"completed_cases": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": total}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
