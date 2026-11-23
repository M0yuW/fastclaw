#!/usr/bin/env python3
"""Four bounded, isolated model-backed finance workflow feasibility probes.

P01/P02 use locked SEC packets. P03/P04 use explicitly synthetic local
Finskills-compatible scripts. This is a pilot, not a confirmatory study.
"""

import argparse
import json
import shutil
import sqlite3
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from run_thesis_event_gateway import create_ephemeral_key, load_plugin, must_call
from run_thesis_event_panel import (
    AGENT_ID, HERE, PLUGIN_PATH, PORT, ROOT, metric_text, prepare_home,
    sha256, source_ref, start_gateway, stop_gateway,
)
from test_thesis_event_integration import locked_episode

FIXTURES = HERE / "workflow_fixtures"
MODEL = "deepseek/deepseek-v4-pro"
PRICING = {MODEL: {"input_per_million": 0.435, "output_per_million": 0.87,
                   "cache_read_per_million": 0.003625}}
CAP_USD = 0.10


def configure(home, synthetic):
    with sqlite3.connect(home / "fastclaw.db") as db:
        row = db.execute("SELECT config FROM agents WHERE id=?", (AGENT_ID,)).fetchone()
        agent = json.loads(row[0])
        agent.update(policy="finance-workflow-pilot", maxToolIterations=8, maxTokens=2500)
        db.execute("UPDATE agents SET config=? WHERE id=?", (json.dumps(agent), AGENT_ID))
        row = db.execute("SELECT id,data FROM configs WHERE kind='setting' AND scope='system' AND name='plugins'").fetchone()
        settings = json.loads(row[1])
        config = settings["entries"]["finance-tools"].setdefault("config", {})
        if synthetic:
            config.update(finskillsPath=str(FIXTURES), evaluationFixture=True)
        db.execute("UPDATE configs SET data=? WHERE id=?", (json.dumps(settings), row[0]))


def event_from_episode(episode_id, fact_ids, external_suffix=""):
    episode, source = locked_episode(episode_id)
    facts = {fact["id"]: fact for fact in episode["facts"]}
    observed = {facts[fact_id]["metric"]: {
        "value": facts[fact_id]["value"], "unit": facts[fact_id]["unit"],
        "fact_id": fact_id,
    } for fact_id in fact_ids}
    event = {
        "external_id": episode["source_id"] + external_suffix,
        "type": "earnings", "as_of": episode["observed_at"],
        "summary": f"{episode['symbol']} {episode['period_label']} SEC event packet: "
                   + metric_text(episode, fact_ids) + ".",
        "sources": [source_ref(source)], "observed_metrics": observed,
    }
    return event, source


class Pilot:
    def __init__(self, case_id, template_db, binary, temp_root, synthetic, spent_so_far):
        self.case_id = case_id
        self.home = prepare_home(template_db, binary, temp_root)
        configure(self.home, synthetic)
        self.token, user_id = create_ephemeral_key(self.home / "fastclaw.db", AGENT_ID)
        self.tenant = {"userId": user_id, "agentId": AGENT_ID, "sessionId": "pilot-seed"}
        self.finance = load_plugin().FinanceToolsPlugin()
        config = {"stateDbPath": str(self.home / "finance-tools.db")}
        if synthetic:
            config.update(finskillsPath=str(FIXTURES), evaluationFixture=True)
        self.finance.initialize(config)
        self.synthetic = synthetic
        self.spent_before = spent_so_far
        self.turns = []

    def turn(self, prompt):
        if self.spent_before + self.cost >= CAP_USD:
            raise RuntimeError("estimated cost cap reached")
        request_body = {
            "messages": [{"role": "user", "content": prompt}], "stream": False,
            "fastclaw": {"eval": True, "include_trace": True,
                         "include_usage_breakdown": True,
                         "server_timeout_ms": 120000, "pricing": PRICING},
        }
        request = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions",
            data=json.dumps(request_body).encode(),
            headers={"Authorization": "Bearer " + self.token,
                     "Content-Type": "application/json",
                     "x-fastclaw-agent-id": AGENT_ID,
                     "x-fastclaw-session-key": "finance-workflow-" + self.case_id},
            method="POST")
        started = time.monotonic()
        response, error = None, None
        try:
            with urllib.request.urlopen(request, timeout=150) as handle:
                response = json.load(handle)
        except urllib.error.HTTPError as exc:
            error = f"HTTP {exc.code}: {exc.read(2048).decode(errors='replace')}"
        except (urllib.error.URLError, TimeoutError) as exc:
            error = str(exc)
        model_calls = (response or {}).get("fastclaw", {}).get("model_calls", [])
        trace = (response or {}).get("fastclaw", {}).get("trace", [])
        item = {
            "prompt": prompt, "response": response, "error": error,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "tool_calls": [entry.get("name") for entry in trace
                           if entry.get("type") == "tool_call"],
            "model_calls": len(model_calls),
            "priced_usage": bool(model_calls) and all(call.get("priced") is True
                                                      for call in model_calls),
            "estimated_cost_usd": sum(call.get("estimated_cost_usd", 0)
                                      for call in model_calls),
        }
        self.turns.append(item)
        if error or not item["priced_usage"] or (response or {}).get("model") != MODEL:
            raise RuntimeError("request error, unpriced usage, or model mismatch")
        if self.spent_before + self.cost >= CAP_USD:
            raise RuntimeError("estimated cost cap reached")
        return item

    @property
    def cost(self):
        return sum(turn["estimated_cost_usd"] for turn in self.turns)

    def ledger_state(self, symbol=None):
        theses = must_call(self.finance, "thesis_list", {}, self.tenant)["theses"]
        alerts = must_call(self.finance, "alert_list", {}, self.tenant)["alerts"]
        detailed = [must_call(self.finance, "thesis_get", {"thesis_id": thesis["id"]},
                              self.tenant) for thesis in theses]
        return {"theses": detailed, "alerts": alerts}


def seed_thesis(pilot, episode_id, fact_ids, text, required):
    episode, source = locked_episode(episode_id)
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": episode["symbol"],
        "title": f"{episode['symbol']} event research thesis",
        "thesis": f"{episode['period_label']} baseline: "
                  f"{metric_text(episode, fact_ids)}. {text}",
        "status": "active", "conviction": 3,
        "catalysts": ["revenue growth", "margin resilience"],
        "invalidations": ["sustained segment weakness", "material margin deterioration"],
        "required_event_metrics": required, "evidence": [source_ref(source)],
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": episode["symbol"], "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [episode["symbol"]],
        "min_match_score": 1,
    }, pilot.tenant)
    return thesis


def review_prompt(case_id, thesis_id, alert_id):
    return (
        "Complete one research-state review for the newly ingested SEC event. "
        "Read the stored thesis and alert via finance tools. Compare only the supplied "
        "periods and metrics, identify support, risk, and missing evidence, and choose "
        "your own decision. Link the stored alert and source hash when recording the "
        "review with the observed thesis version; then acknowledge the alert with its "
        "observed version. A missing metric in the packet is not necessarily missing "
        "from the SEC filing. Do not trade. "
        f"Case {case_id}; thesis ID {thesis_id}; alert ID {alert_id}."
    )


def ingest(pilot, symbol, event):
    return must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": event,
    }, pilot.tenant)


def run_p01(pilot):
    thesis = seed_thesis(
        pilot, "FSEC-AMD-01", ["AMD-Q2-REV", "AMD-Q2-GM", "AMD-Q2-GAME"],
        "Track total-company growth and GAAP margin alongside Gaming segment risk; "
        "do not infer a sustained recovery from one improved quarter.",
        ["quarterly_revenue", "gross_margin", "gaming_revenue"])
    e1, _ = event_from_episode("FSEC-AMD-02", ["AMD-Q3-REV", "AMD-Q3-GM", "AMD-Q3-GAME"])
    first = ingest(pilot, "AMD", e1)
    a1 = first["results"][0]["alert"]
    pilot.turn(review_prompt("P01", thesis["id"], a1["id"]))
    duplicate = ingest(pilot, "AMD", e1)
    e2, _ = event_from_episode("FSEC-AMD-03", ["AMD-Q4-REV", "AMD-Q4-GM", "AMD-Q4-GAME"])
    second = ingest(pilot, "AMD", e2)
    a2 = second["results"][0]["alert"]
    pilot.turn(review_prompt("P01", thesis["id"], a2["id"]))
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    checks = {
        "two_distinct_alerts": len(state["alerts"]) == 2,
        "duplicate_suppressed": duplicate["created"] == 0 and duplicate["deduplicated"] == 1,
        "two_reviews": len(reviews) == 2,
        "two_version_increments": state["theses"][0]["thesis"]["version"] == 3,
        "both_alerts_acknowledged": all(a["status"] == "acknowledged" for a in state["alerts"]),
        "reviews_link_distinct_alerts": len({r["alert_id"] for r in reviews}) == 2,
    }
    return state, checks, {"duplicate_ingest": duplicate}


def run_p02(pilot):
    thesis = seed_thesis(
        pilot, "FSEC-NVDA-01", ["NVDA-Q1-REV", "NVDA-Q1-GM", "NVDA-Q1-DC"],
        "A substantive update requires current total revenue, GAAP gross margin, "
        "and Data Center revenue; preserve uncertainty if the packet is incomplete.",
        ["quarterly_revenue", "gross_margin", "data_center_revenue"])
    partial, _ = event_from_episode("FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-DC"])
    first = ingest(pilot, "NVDA", partial)
    a1 = first["results"][0]["alert"]
    pilot.turn(review_prompt("P02", thesis["id"], a1["id"]))
    interim = pilot.ledger_state()
    complete, _ = event_from_episode(
        "FSEC-NVDA-02", ["NVDA-Q2-REV", "NVDA-Q2-GM", "NVDA-Q2-DC"],
        external_suffix="-complete-packet-v1")
    second = ingest(pilot, "NVDA", complete)
    a2 = second["results"][0]["alert"]
    pilot.turn(review_prompt("P02", thesis["id"], a2["id"]))
    state = pilot.ledger_state()
    reviews = state["theses"][0]["reviews"]
    checks = {
        "partial_review_deferred": len(interim["theses"][0]["reviews"]) == 1
            and interim["theses"][0]["reviews"][0]["decision"] == "needs_review"
            and interim["theses"][0]["thesis"]["version"] == 3
            and interim["theses"][0]["thesis"]["actionability"] == "blocked",
        "first_missing_metric_recorded": bool(reviews)
            and any(r["missing_metrics"] == ["gross_margin"] for r in reviews),
        "complete_packet_distinct_alert": len(state["alerts"]) == 2,
        "two_reviews": len(reviews) == 2,
        "second_review_complete": any(r["alert_id"] == a2["id"] and not r["missing_metrics"]
                                      for r in reviews),
        "two_version_increments": state["theses"][0]["thesis"]["version"] == 4,
        "evidence_hold_resolved": state["theses"][0]["thesis"]["actionability"] == "available",
        "both_alerts_acknowledged": all(a["status"] == "acknowledged" for a in state["alerts"]),
    }
    return state, checks, {"interim": interim}


def run_p03(pilot):
    pilot.turn(
        "This is a synthetic, non-investment research workflow using fixture tickers "
        "FICA and FICB. Call finance-tools__screen_stocks for both with "
        "require_complete=true. Read the tool's retained and rejected sets. Create "
        "one preliminary thesis via finance-tools__thesis_save only for a complete "
        "retained candidate; name its key metrics, missingness boundary, and synthetic "
        "fixture provenance. Do not create a thesis for a rejected candidate. Do not "
        "trade or call external market-data tools. Case P03.")
    state = pilot.ledger_state()
    names = [name for turn in pilot.turns for name in turn["tool_calls"]]
    theses = [entry["thesis"] for entry in state["theses"]]
    checks = {
        "screen_tool_used": "finance-tools__screen_stocks" in names,
        "one_thesis_created": len(theses) == 1,
        "complete_candidate_only": len(theses) == 1 and theses[0]["symbol"] == "FICA",
        "no_alerts": len(state["alerts"]) == 0,
        "no_trade_tool": all("trade" not in (name or "") for name in names),
    }
    return state, checks, {}


def run_p04(pilot):
    pilot.turn(
        "This is a synthetic portfolio-risk diagnostic, not a live account. "
        "Holdings are FICA 70% and FICB 30%; the concentration policy limit for "
        "one holding is 50%. Call finance-tools__portfolio_risk with the weights "
        "and view=concentration. Explain the measured exposure and a reversible "
        "human-review recommendation. Do not trade, change holdings, or create "
        "ledger records. Case P04.")
    state = pilot.ledger_state()
    names = [name for turn in pilot.turns for name in turn["tool_calls"]]
    final = (pilot.turns[-1]["response"] or {}).get("choices", [{}])[0].get("message", {}).get("content", "")
    checks = {
        "risk_tool_used": "finance-tools__portfolio_risk" in names,
        "no_ledger_mutation": not state["theses"] and not state["alerts"],
        "limit_breach_explained": "70" in final and "50" in final,
        "human_boundary_stated": "human" in final.lower() or "approval" in final.lower(),
        "no_trade_tool": all("trade" not in (name or "") for name in names),
    }
    return state, checks, {}


CASES = [("P01", run_p01, False), ("P02", run_p02, False),
         ("P03", run_p03, True), ("P04", run_p04, True)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", type=Path, required=True)
    parser.add_argument("--gateway-binary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing to overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("template DB and Gateway binary required")
    # Source-lock validation and deterministic fixture smoke checks precede paid calls.
    for episode_id in ("FSEC-AMD-01", "FSEC-AMD-02", "FSEC-AMD-03",
                       "FSEC-NVDA-01", "FSEC-NVDA-02"):
        locked_episode(episode_id)
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), HERE / "run_thesis_event_panel.py",
             HERE / "run_thesis_event_gateway.py", HERE / "test_thesis_event_integration.py",
             HERE / "evidence.json", HERE / "source-lock.json", PLUGIN_PATH,
             ROOT / "internal/policy/defaults.go", ROOT / "internal/policy/engine.go",
             *FIXTURES.rglob("*.py")]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest["gateway_binary_sha256"] = sha256(args.gateway_binary)
    manifest["gateway_template_db_sha256"] = sha256(args.template_db)
    manifest["estimated_spend_stop_usd"] = CAP_USD
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="finance-workflow-pilot-") as temp_root:
        for case_id, func, synthetic in CASES:
            if spent >= CAP_USD:
                break
            pilot = Pilot(case_id, args.template_db, args.gateway_binary,
                          temp_root, synthetic, spent)
            process, log = start_gateway(pilot.home)
            state, checks, extras, error = None, {}, {}, None
            try:
                state, checks, extras = func(pilot)
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
            finally:
                stop_gateway(process, log)
            spent += pilot.cost
            case_dir = args.output_dir / case_id
            case_dir.mkdir()
            result = {
                "case_id": case_id, "synthetic_tool_fixture": synthetic,
                "status": "mechanical_pass" if error is None and all(checks.values()) else "needs_review",
                "error": error, "checks": checks, "state": state,
                "extras": extras, "turns": pilot.turns,
                "estimated_cost_usd": pilot.cost,
            }
            (case_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            shutil.copy2(pilot.home / "finance-tools.db", case_dir / "finance-tools.db")
            print(json.dumps({"case_id": case_id, "status": result["status"],
                              "error": error, "checks": checks,
                              "turns": len(pilot.turns), "estimated_cost_usd": pilot.cost},
                             ensure_ascii=False), flush=True)
            if error or any(not turn["priced_usage"] for turn in pilot.turns):
                print("STOP: request error or uncertain pricing", flush=True)
                break
    print(json.dumps({"completed_cases": len(list(args.output_dir.glob("*/result.json"))),
                      "estimated_cost_usd": spent}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
