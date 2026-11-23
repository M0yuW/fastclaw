#!/usr/bin/env python3
"""Free Gateway replay of typed-answer acceptance and rejection on seen FITB.

The provider is a local script. This tests actual Gateway/tool/ledger/gate
plumbing, not autonomous model behavior or financial-insight quality.
"""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import build_postcorrection_v4_event_preflight as source_batch
import build_insight_candidate_prompt_v1 as candidate_contract
import run_finance_gateway_fault_replay as local
import run_finance_workflow_pilot as base
import run_postcorrection_gateway_replay_v2 as gateway
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_insight_candidate_v1 import canonical_state, render_review_card


class DynamicCandidateProvider:
    def __init__(self, scripted_calls: list[bytes], final_builder):
        self.scripted_calls = list(scripted_calls)
        self.final_builder = final_builder
        self.requests = []
        parent = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                size = int(self.headers.get("Content-Length", "0"))
                request = json.loads(self.rfile.read(size))
                parent.requests.append(request)
                index = len(parent.requests) - 1
                if self.path != "/chat/completions" or index > len(parent.scripted_calls):
                    self.send_error(500, "unexpected local scripted request")
                    return
                payload = (parent.scripted_calls[index]
                           if index < len(parent.scripted_calls)
                           else local.text_stream(json.dumps(parent.final_builder(),
                                                             ensure_ascii=False)))
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


def run_case(template_db: Path, binary: Path, fixture: dict, facts: dict,
             temp_root: str, wrong: bool) -> dict:
    branch = "contradicted" if wrong else "source_derived"
    pilot = base.Pilot("insight-candidate-" + branch, template_db, binary,
                       temp_root, False, 0.0)
    thesis = must_call(pilot.finance, "thesis_save", fixture["seed_thesis"],
                       pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "FITB", "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": ["FITB"], "min_match_score": 1,
    }, pilot.tenant)
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": "FITB", "event": fixture["event"],
    }, pilot.tenant)["results"][0]["alert"]
    evidence = [fixture["seed_thesis"]["evidence"][0],
                fixture["event"]["sources"][0]]
    calls = [
        local.tool_stream("read-thesis", "finance-tools__thesis_get",
                          {"thesis_id": thesis["id"]}),
        local.tool_stream("read-alert", "finance-tools__alert_list", {}),
        local.tool_stream("save-review", "finance-tools__thesis_record_review", {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": thesis["version"],
            "event": {"summary": alert["event"]["summary"]},
            "impact": "mixed", "decision": "needs_review",
            "rationale": "The selected source rows show mixed earnings and credit signals.",
            "evidence": evidence, "next_review_at": "2026-11-30",
            "causal_claims": [],
        }),
        local.tool_stream("ack-alert", "finance-tools__alert_update", {
            "alert_id": alert["id"], "status": "acknowledged",
            "expected_version": alert["version"],
        }),
    ]

    def final_candidate() -> dict:
        assertion = canonical_state(pilot.ledger_state())
        if wrong:
            assertion["next_review_at"] = "2026-01-31"
        return {
            "claims": [{"op": "delta", "metric": "gaap_pretax_income",
                        "value": "30" if wrong else "29",
                        "unit": "USD_million", "basis": "GAAP"}],
            "interpretation": {
                "implication": "Reported improvement is bounded by credit cost.",
                "counterevidence": "The provision increased.",
                "uncertainty": "Provision composition needs further research.",
            },
            "asserted_state": assertion,
        }

    with DynamicCandidateProvider(calls, final_candidate) as provider:
        local.configure_provider(pilot.home, provider.url)
        process, log = base.start_gateway(pilot.home)
        try:
            response = gateway.gateway_turn(
                pilot, candidate_contract.candidate_prompt(
                    fixture, thesis["id"], alert["id"]),
                "FITB-" + branch)
        finally:
            base.stop_gateway(process, log)
        requests = provider.requests
    state = pilot.ledger_state()
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    candidate = json.loads(final)
    card = render_review_card(facts, candidate, state)
    trace = response.get("fastclaw", {}).get("trace", [])
    tool_calls = [item for item in trace if item.get("type") == "tool_call"]
    tool_results = [item for item in trace if item.get("type") == "tool_result"]
    provider_prompt = json.dumps(requests[0], ensure_ascii=False) if requests else ""
    held = state["theses"][0]["thesis"]
    checks = {
        "local_provider_five_requests": len(requests) == 5,
        "candidate_schema_prompt_delivered":
            "exactly three top-level keys" in provider_prompt
            and "asserted_state" in provider_prompt,
        "four_tool_calls_paired": len(tool_calls) == len(tool_results) == 4
            and {item["id"] for item in tool_calls}
            == {item["id"] for item in tool_results},
        "one_review_and_blocked_state": len(state["theses"][0]["reviews"]) == 1
            and held["decision_hold"] and held["actionability"] == "blocked"
            and state["alerts"][0]["status"] == "acknowledged",
        "gate_expected_branch": card["status"] == (
            "held" if wrong else "candidate_for_qualitative_review"),
        "no_quality_pass_inferred": card["quality_pass"] is None,
    }
    if wrong:
        checks["both_faults_visible"] = set(card["issues"]) == {
            "numeric_claims_unverified_or_uncovered",
            "state_claim_contradicted_by_ledger",
        }
    else:
        checks["card_uses_authoritative_values"] = (
            card["source_derived_assertions"][0]["verified_result"] == "29"
            and card["canonical_state"]["next_review_at"] == "2026-11-30")
    return {"branch": branch, "checks": checks,
            "all_checks_passed": all(checks.values()),
            "card": card, "model_observations": 0,
            "external_provider_requests": 0,
            "estimated_external_cost_usd": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-db", required=True, type=Path)
    parser.add_argument("--gateway-binary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise ValueError("output directory exists; refusing overwrite")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")
    prepared = source_batch.preflight()
    fixture = next(item for item in prepared["fixtures"]
                   if item["runtime_symbol"] == "FITB")
    packet_path = (source_batch.FIRST_PACKETS.get("FITB")
                   or source_batch.DECLARED_PACKETS["FITB"])
    packet = json.loads(packet_path.read_text())
    facts = source_batch._normalize("FITB", packet)["facts"]
    with tempfile.TemporaryDirectory(prefix="insight-candidate-gateway-") as temp_root:
        results = [run_case(args.template_db, args.gateway_binary, fixture,
                            facts, temp_root, wrong)
                   for wrong in (False, True)]
    summary = {"status": "free_scripted_candidate_gateway_replay",
               "branches": len(results),
               "all_checks_passed": all(item["all_checks_passed"] for item in results),
               "model_observations": 0, "external_provider_requests": 0,
               "estimated_external_cost_usd": 0}
    paths = [Path(__file__), Path(source_batch.__file__), Path(local.__file__),
             Path(gateway.__file__), Path(candidate_contract.__file__),
             HERE / "verify_insight_candidate_v1.py",
             HERE / "validate_structured_financial_claims_v1.py",
             packet_path, PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for result in results:
        (args.output_dir / f"{result['branch']}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n" for path in sorted(
            path for path in args.output_dir.iterdir() if path.suffix == ".json")))
    print(json.dumps(summary, indent=2))
    if not summary["all_checks_passed"]:
        raise AssertionError("scripted candidate Gateway replay failed")


if __name__ == "__main__":
    main()
