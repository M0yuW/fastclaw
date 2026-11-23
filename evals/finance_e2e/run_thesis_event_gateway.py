#!/usr/bin/env python3
"""One bounded, isolated SEC event-to-thesis Gateway validation attempt.

This script is deliberately separate from the frozen Stage 2 results. It
seeds an isolated plugin ledger, makes one model-backed Gateway request, and
grades persisted state. It never prints the ephemeral API key.
"""

import argparse
import hashlib
import importlib.util
import json
import secrets
import sqlite3
import time
import urllib.error
import urllib.request
from pathlib import Path

from test_thesis_event_integration import HERE, ROOT, PLUGIN_PATH, locked_episode


def load_plugin():
    spec = importlib.util.spec_from_file_location("finance_event_plugin", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def must_call(plugin, name, args, tenant):
    result = plugin.execute(name, args, tenant)
    if not result["ok"]:
        raise RuntimeError(f"{name} failed: {result['errors']}")
    return result["data"]


def create_ephemeral_key(database, agent_id):
    token = "fc_" + secrets.token_hex(32)
    key_id = "k_finance_event_" + secrets.token_hex(8)
    with sqlite3.connect(database) as connection:
        row = connection.execute("SELECT user_id FROM agents WHERE id=?", (agent_id,)).fetchone()
        if row is None:
            raise ValueError(f"agent absent from isolated snapshot: {agent_id}")
        user_id = row[0]
        connection.execute(
            "INSERT INTO apikeys(id,user_id,name,key_hash,key_prefix) VALUES (?,?,?,?,?)",
            (key_id, user_id, "finance-event-one-attempt", hashlib.sha256(token.encode()).hexdigest(), token[:10]),
        )
        connection.execute(
            "INSERT INTO apikey_agents(apikey_id,agent_id) VALUES (?,?)", (key_id, agent_id)
        )
    return token, user_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, required=True, help="fresh isolated FASTCLAW_HOME")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:18955")
    parser.add_argument("--agent-id", default="finance-coordinator")
    args = parser.parse_args()

    database = args.home / "fastclaw.db"
    ledger = args.home / "finance-tools.db"
    if not database.is_file() or not ledger.is_file():
        raise ValueError("isolated Gateway and finance ledger must already exist")
    if args.output_dir.exists():
        raise ValueError("output directory already exists; refusing to overwrite an attempt")

    q2, q2_source = locked_episode("FSEC-AMD-01")
    q3, q3_source = locked_episode("FSEC-AMD-02")
    q2_facts = {item["id"]: item["value"] for item in q2["facts"]}
    q3_facts = {item["id"]: item["value"] for item in q3["facts"]}
    token, user_id = create_ephemeral_key(database, args.agent_id)
    tenant = {"userId": user_id, "agentId": args.agent_id, "sessionId": "event-fixture-seed"}
    plugin = load_plugin().FinanceToolsPlugin()
    plugin.initialize({"stateDbPath": str(ledger)})
    if must_call(plugin, "thesis_list", {}, tenant)["count"]:
        raise ValueError("ledger is not empty; use a new isolated home")

    q2_source_ref = {"id": q2_source["id"], "url": q2_source["url"], "sha256": q2_source["sha256"]}
    q3_source_ref = {"id": q3_source["id"], "url": q3_source["url"], "sha256": q3_source["sha256"]}
    thesis = must_call(plugin, "thesis_save", {
        "market": "US", "symbol": "AMD", "title": "AMD segment-mix research thesis",
        "thesis": (
            f"Q2 2024 GAAP revenue USD {q2_facts['AMD-Q2-REV']} million, "
            f"GAAP gross margin {q2_facts['AMD-Q2-GM']}%, and Gaming revenue "
            f"USD {q2_facts['AMD-Q2-GAME']} million. Revenue growth is a positive "
            "signal, while persistent Gaming weakness is a segment-mix risk."
        ),
        "status": "active", "conviction": 3,
        "catalysts": ["revenue growth"], "invalidations": ["Gaming weakness"],
        "evidence": [q2_source_ref],
    }, tenant)["thesis"]
    must_call(plugin, "watchlist_save", {
        "market": "US", "symbol": "AMD", "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": ["Gaming revenue"], "min_match_score": 1,
    }, tenant)
    event = {
        "external_id": q3["source_id"], "type": "earnings", "as_of": q3["observed_at"],
        "summary": (
            f"AMD Q3 2024 GAAP revenue was USD {q3_facts['AMD-Q3-REV']} million, "
            f"GAAP gross margin was {q3_facts['AMD-Q3-GM']}%, and Gaming revenue "
            f"was USD {q3_facts['AMD-Q3-GAME']} million."
        ),
        "sources": [q3_source_ref],
    }
    ingested = must_call(plugin, "event_alert_ingest", {
        "market": "US", "symbol": "AMD", "event": event,
    }, tenant)
    if ingested["created"] != 1:
        raise AssertionError(f"expected one event alert, got {ingested}")
    alert = ingested["results"][0]["alert"]

    prompt = (
        "You are performing a bounded research-state review, not investment advice. "
        "Use the finance-tools__thesis_get and finance-tools__alert_list tools to inspect "
        "the current AMD thesis and new alert. The Q3 SEC event is already ingested. "
        "Compare the Q2 baseline in the thesis with the Q3 figures in the alert; "
        "explain both improvement and continuing Gaming risk. Then call "
        "finance-tools__thesis_record_review exactly once, using the thesis ID and "
        "expected_version you read, evidence containing the Q3 source ID and hash, "
        "and a conservative research-state decision. Preserve active status and "
        "conviction 3: the evidence does not justify changing either. After a "
        "successful review, call finance-tools__alert_update to acknowledge the "
        "alert with its observed version. No trade or portfolio action. "
        f"Thesis ID: {thesis['id']}; alert ID: {alert['id']}."
    )
    request_body = {
        "messages": [{"role": "user", "content": prompt}], "stream": False,
        "fastclaw": {
            "eval": True, "include_trace": True, "include_usage_breakdown": True,
            "server_timeout_ms": 120000,
        },
    }
    request = urllib.request.Request(
        args.base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(request_body).encode(),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "x-fastclaw-agent-id": args.agent_id,
            "x-fastclaw-session-key": "finance-event-" + secrets.token_hex(8),
        },
        method="POST",
    )
    started = time.monotonic()
    response = None
    error = None
    try:
        with urllib.request.urlopen(request, timeout=150) as handle:
            response = json.load(handle)
    except urllib.error.HTTPError as exc:
        error = f"HTTP {exc.code}: {exc.read(4096).decode(errors='replace')}"
    except (urllib.error.URLError, TimeoutError) as exc:
        error = str(exc)
    elapsed = time.monotonic() - started

    fetched = must_call(plugin, "thesis_get", {"thesis_id": thesis["id"]}, tenant)
    alerts = must_call(plugin, "alert_list", {"symbol": "AMD"}, tenant)["alerts"]
    reviews = fetched["reviews"]
    actual = fetched["thesis"]
    checks = {
        "one_review": len(reviews) == 1,
        "version_once": actual["version"] == thesis["version"] + 1,
        "status_preserved": actual["status"] == "active",
        "conviction_preserved": actual["conviction"] == 3,
        "source_recorded": bool(reviews) and any(
            source.get("sha256") == q3_source_ref["sha256"]
            for source in reviews[0]["event"]["sources"]
        ),
        "alert_acknowledged": len(alerts) == 1 and alerts[0]["status"] == "acknowledged",
    }
    result = {
        "case_id": "FSEC-AMD-02-thesis-event-gateway-smoke",
        "status": "pass" if error is None and all(checks.values()) else "fail",
        "error": error, "elapsed_seconds": round(elapsed, 3), "checks": checks,
        "before": {"thesis_version": thesis["version"], "alert_version": alert["version"]},
        "after": {
            "thesis_version": actual["version"], "status": actual["status"],
            "conviction": actual["conviction"], "reviews": len(reviews),
            "alerts": [{"status": item["status"], "version": item["version"]} for item in alerts],
        },
        "gateway_response": response,
    }
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    manifest = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in [
        HERE / "evidence.json", HERE / "source-lock.json", PLUGIN_PATH,
        ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go",
        ROOT / "internal/plugin/tool_adapter.go",
        Path(__file__),
    ]}
    manifest["gateway_binary"] = hashlib.sha256((args.home / "fastclaw").read_bytes()).hexdigest()
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("case_id", "status", "error", "elapsed_seconds", "checks")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
