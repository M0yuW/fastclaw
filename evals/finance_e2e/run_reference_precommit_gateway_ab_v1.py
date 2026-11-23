#!/usr/bin/env python3
"""Free scripted Gateway A/B for the optional source-bound review guard.

Only local loopback model-interface responses are used. The original saved
model review arguments are fixed across arms; B enables a trusted-catalog
pre-commit veto and, after an error, submits a deterministic review hold.
This is a developmental seen-case mechanism check, not a quality-rate study.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from build_reference_source_distinct_event_fixtures_v1 import preflight
from run_finance_gateway_fault_replay import (ScriptedProvider,
                                              configure_provider, text_stream,
                                              tool_stream)
from run_finance_workflow_pilot import Pilot, start_gateway, stop_gateway
from run_postcorrection_gateway_replay_v2 import gateway_turn
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


JUDGMENTS = (HERE / "results" /
             "2026-10-26-reference-source-distinct-insight-judgment-v1")
CASES = ("J-a43fcf41e603f011", "J-12d921bb4b32208c")
VETO_SYMBOLS = frozenset({"JKHY"})


def _review_call(packet: dict) -> dict:
    calls = [json.loads(item["arguments"])
             for item in packet["tool_evidence"]
             if item.get("type") == "tool_call"
             and item.get("name") == "finance-tools__thesis_record_review"]
    if len(calls) != 1:
        raise ValueError("exactly one saved review call required")
    return calls[0]


def _guard_catalog(fixture: dict) -> dict:
    catalog = fixture["catalog"]
    return {"version": "review-arithmetic-guard-catalog-v1", "cases": [{
        "symbol": fixture["runtime_symbol"],
        "baseline_source_sha256": catalog["baseline"]["source_sha256"],
        "event_source_sha256": catalog["event"]["source_sha256"],
        "rows": catalog["rows"],
    }]}


def _enable_guard(home: Path, catalog_path: Path) -> None:
    with sqlite3.connect(home / "fastclaw.db") as database:
        row = database.execute(
            "SELECT id,data FROM configs WHERE kind='setting' AND scope='system' "
            "AND name='plugins'").fetchone()
        if row is None:
            raise ValueError("isolated Gateway has no plugin settings")
        settings = json.loads(row[1])
        settings["entries"]["finance-tools"].setdefault("config", {})[
            "reviewArithmeticGuardCatalogPath"] = str(catalog_path)
        database.execute("UPDATE configs SET data=? WHERE id=?",
                         (json.dumps(settings), row[0]))


def _run_arm(template_db: Path, binary: Path, fixture: dict, packet: dict,
             branch: str, temp_root: Path, output_dir: Path) -> dict:
    symbol = fixture["runtime_symbol"]
    pilot = Pilot(f"review-guard-{symbol}-{branch}", template_db, binary,
                  str(temp_root), False, 0.0)
    catalog_path = pilot.home / "review-guard-catalog.json"
    catalog_path.write_text(json.dumps(_guard_catalog(fixture), sort_keys=True))
    thesis = must_call(pilot.finance, "thesis_save", fixture["seed_thesis"],
                       pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": symbol, "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": [symbol],
        "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": symbol, "event": fixture["event"],
    }, pilot.tenant)["results"][0]["alert"]
    original = _review_call(packet)
    review = {**original, "thesis_id": thesis["id"],
              "alert_id": alert["id"], "expected_version": thesis["version"]}
    corrected = {
        "thesis_id": thesis["id"], "alert_id": alert["id"],
        "expected_version": thesis["version"],
        "event": {"summary": alert["event"]["summary"]},
        "impact": "mixed", "decision": "needs_review",
        "rationale": "The proposed review contains a source-arithmetic contradiction. "
                     "Hold this research thesis pending a corrected comparison.",
        "evidence": [fixture["seed_thesis"]["evidence"][0],
                     fixture["event"]["sources"][0]],
        "causal_claims": [],
    }
    calls = [
        tool_stream("read-thesis", "finance-tools__thesis_get",
                    {"thesis_id": thesis["id"]}),
        tool_stream("read-alert", "finance-tools__alert_list", {}),
        tool_stream("original-review", "finance-tools__thesis_record_review", review),
    ]
    should_veto = branch == "B" and symbol in VETO_SYMBOLS
    if should_veto:
        calls.append(tool_stream("safe-hold", "finance-tools__thesis_record_review",
                                 corrected))
    calls.extend([
        tool_stream("ack-alert", "finance-tools__alert_update", {
            "alert_id": alert["id"], "status": "acknowledged",
            "expected_version": alert["version"],
        }),
        text_stream("Local scripted research review complete."),
    ])
    with ScriptedProvider(calls) as provider:
        configure_provider(pilot.home, provider.url)
        if branch == "B":
            _enable_guard(pilot.home, catalog_path)
        process, log = start_gateway(pilot.home)
        try:
            response = gateway_turn(pilot, "Fixed local review-call replay.",
                                    symbol + branch)
        finally:
            stop_gateway(process, log)
        requests = provider.received
        unused = len(provider.responses)
    state = pilot.ledger_state()
    trace = response.get("fastclaw", {}).get("trace", [])
    tool_calls = [item for item in trace if item.get("type") == "tool_call"]
    tool_results = [item for item in trace if item.get("type") == "tool_result"]
    error_result = [item for item in tool_results
                    if item.get("id") == "original-review"]
    error_text = json.dumps(error_result, ensure_ascii=False)
    stored = state["theses"][0]
    checks = {
        "only_scripted_provider_requests": requests == len(calls) and unused == 0,
        "tool_calls_paired": len(tool_calls) == len(tool_results)
            and {item["id"] for item in tool_calls}
            == {item["id"] for item in tool_results},
        "one_linked_review": len(stored["reviews"]) == 1
            and stored["reviews"][0]["alert_id"] == alert["id"],
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "guard_error_visible": ("review_arithmetic_contradiction" in error_text)
            if should_veto else ("review_arithmetic_contradiction" not in error_text),
        "expected_state": (
            stored["thesis"]["actionability"] == "blocked"
            and stored["thesis"]["decision_hold"]
            and stored["reviews"][0]["decision"] == "needs_review"
        ) if should_veto or original["decision"] == "needs_review" else (
            stored["thesis"]["actionability"] == "available"
            and not stored["thesis"]["decision_hold"]
            and stored["reviews"][0]["decision"] == "maintain"
        ),
        "status_conviction_preserved":
            stored["thesis"]["status"] == "active"
            and stored["thesis"]["conviction"] == 3,
    }
    branch_dir = output_dir / symbol / branch
    branch_dir.mkdir(parents=True)
    shutil.copy2(pilot.home / "finance-tools.db", branch_dir / "finance-tools.db")
    (branch_dir / "trace.json").write_text(json.dumps(trace, indent=2))
    return {"symbol": symbol, "branch": branch,
            "masked_id": packet["masked_id"],
            "original_model_decision": original["decision"],
            "provider_requests": requests, "external_provider_requests": 0,
            "model_observations": 0, "quality_pass": None,
            "checks": checks, "all_checks_passed": all(checks.values()),
            "saved_decision": stored["reviews"][0]["decision"],
            "review_rationale_matches_original":
                stored["reviews"][0]["rationale"] == original["rationale"],
            "review_rationale_guard_sanitized":
                stored["reviews"][0]["rationale"].startswith(
                    "Source-bound review check flagged "),
            "actionability": stored["thesis"]["actionability"],
            "decision_hold": stored["thesis"]["decision_hold"],
            "review_error_visible": "review_arithmetic_contradiction" in error_text}


def run(template_db: Path, binary: Path, output_dir: Path) -> dict:
    if output_dir.exists():
        raise ValueError("output path exists; refusing to overwrite")
    fixtures = {item["runtime_symbol"]: item for item in preflight()["fixtures"]}
    output_dir.mkdir(parents=True)
    results = []
    with tempfile.TemporaryDirectory(prefix="reference-guard-gateway-ab-") as temp:
        for masked_id in CASES:
            packet = json.loads((JUDGMENTS / "masked_packets" /
                                 f"{masked_id}.json").read_text())
            fixture = fixtures[packet["source_packet"]["symbol"]]
            for branch in ("A", "B"):
                results.append(_run_arm(template_db, binary, fixture, packet,
                                        branch, Path(temp), output_dir))
    summary = {
        "study_type": "developmental_scripted_gateway_precommit_ab",
        "branches": len(results), "all_checks_passed":
            all(item["all_checks_passed"] for item in results),
        "model_observations": 0, "external_provider_requests": 0,
        "estimated_external_cost_usd": 0, "quality_pass": None,
        "results": results,
    }
    (output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    manifest = {"gateway_binary_sha256": sha256(binary),
                "gateway_template_db_sha256": sha256(template_db),
                "plugin_sha256": sha256(PLUGIN_PATH),
                "guard_sha256": sha256(ROOT / "plugins/finance-tools/review_arithmetic_guard.py"),
                "script_sha256": sha256(Path(__file__)),
                "provider": "local_scripted_loopback_no_external_api"}
    (output_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    paths = sorted([output_dir / "SUMMARY.json", output_dir / "MANIFEST.json",
                    *output_dir.glob("*/*/trace.json"),
                    *output_dir.glob("*/*/finance-tools.db")])
    (output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.relative_to(output_dir)}\n" for path in paths))
    if not summary["all_checks_passed"]:
        raise AssertionError("scripted Gateway review-guard replay failed")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    print(json.dumps(run(args.template_db, args.gateway_binary, args.output_dir),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
