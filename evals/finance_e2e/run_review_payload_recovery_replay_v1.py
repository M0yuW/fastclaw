#!/usr/bin/env python3
"""Free scripted Gateway replay of a malformed review followed by correction.

This tests error propagation and ledger state, not autonomous model recovery.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import run_finance_gateway_fault_replay as local
import run_finance_workflow_pilot as base
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256


def run(template_db: Path, binary: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="review-payload-recovery-") as root:
        pilot = base.Pilot("review-payload-recovery", template_db, binary,
                           root, False, 0.0)
        thesis, alert = local.seed(pilot)
        evidence = alert["event"]["sources"][0]
        common = {
            "thesis_id": thesis["id"], "alert_id": alert["id"],
            "expected_version": thesis["version"],
            "event": {"summary": alert["event"]["summary"]},
            "impact": "mixed", "decision": "needs_review",
        }
        malformed = {
            **common,
            "rationale": (
                "Selected revenue is 100 USD million but the evidence is incomplete"
                '", "evidence": [{"id": "fixture", "sha256": "'
                + "a" * 64 + '"}], "next_review_at": "2026-11-30"'
            ),
        }
        corrected = {
            **common,
            "rationale": "Selected revenue is 100 USD million; the evidence is incomplete.",
            "evidence": [evidence], "next_review_at": "2026-11-30",
            "causal_claims": [],
        }
        responses = [
            local.tool_stream("malformed-review", "finance-tools__thesis_record_review",
                              malformed),
            local.tool_stream("corrected-review", "finance-tools__thesis_record_review",
                              corrected),
            local.tool_stream("acknowledge", "finance-tools__alert_update", {
                "alert_id": alert["id"], "status": "acknowledged",
                "expected_version": alert["version"],
            }),
            local.text_stream("Corrected review persisted; research decision is on hold."),
        ]
        with local.ScriptedProvider(responses) as provider:
            local.configure_provider(pilot.home, provider.url)
            process, log = base.start_gateway(pilot.home)
            try:
                response = local.gateway_turn(pilot, "review-payload-recovery")
            finally:
                base.stop_gateway(process, log)
            requests = provider.requests
            received = provider.received
            unused = len(provider.responses)
        state = pilot.ledger_state()

    trace = response.get("fastclaw", {}).get("trace", [])
    calls = [item for item in trace if item.get("type") == "tool_call"]
    results = [item for item in trace if item.get("type") == "tool_result"]
    errors = []
    for item in results:
        try:
            payload = json.loads(item.get("result") or "{}")
        except json.JSONDecodeError:
            continue
        errors.extend(error.get("code") for error in payload.get("errors", []))
    saved = state["theses"][0]
    reviews = saved["reviews"]
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content", "")
    checks = {
        "local_provider_only": received == 4 and unused == 0,
        "malformed_error_visible_to_next_request":
            len(requests) >= 2
            and "malformed_review_payload" in json.dumps(requests[1]),
        "malformed_write_rejected": errors.count("malformed_review_payload") == 1,
        "calls_results_paired": len(calls) == len(results) == 3
            and {item["id"] for item in calls} == {item["id"] for item in results},
        "only_corrected_review_persisted": len(reviews) == 1
            and reviews[0]["alert_id"] == alert["id"]
            and reviews[0]["evidence"] == [evidence]
            and '"evidence":' not in reviews[0]["rationale"],
        "hold_and_date_persisted": saved["thesis"]["decision_hold"]
            and saved["thesis"]["actionability"] == "blocked"
            and saved["thesis"]["next_review_at"] == "2026-11-30",
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "final_matches_script": final == (
            "Corrected review persisted; research decision is on hold."),
    }
    return {
        "status": "free_scripted_error_recovery_not_model_quality",
        "checks": checks, "all_checks_passed": all(checks.values()),
        "error_codes": errors, "tool_calls": len(calls),
        "model_observations": 0, "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
    }


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
    result = run(args.template_db, args.gateway_binary)
    paths = [Path(__file__), Path(local.__file__),
             HERE / "run_finance_workflow_pilot.py", PLUGIN_PATH]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api")
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in (args.output_dir / "manifest.json",
                     args.output_dir / "result.json")))
    print(json.dumps(result, indent=2))
    if not result["all_checks_passed"]:
        raise AssertionError("scripted review-payload recovery failed")


if __name__ == "__main__":
    main()
