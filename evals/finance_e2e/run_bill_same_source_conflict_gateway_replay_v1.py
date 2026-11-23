#!/usr/bin/env python3
"""Free isolated Gateway replay of BILL same-source conflict handling.

The provider is a deterministic loopback script, never a paid model. A second
branch deliberately omits one source claim to expose the ingestion precondition.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import run_finance_gateway_fault_replay as local
import run_finance_workflow_pilot as base
from run_thesis_event_gateway import must_call
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_reference_source_row_packet_v1 import verify


PACKET_PATH = HERE / "bill_reference_source_row_audit_v1.json"
SELECTION_PATH = HERE / "results/2026-10-25-reference-source-pair-selection-v1/SOURCE-PAIRS.json"


def bill_source() -> tuple[dict, dict]:
    if verify(PACKET_PATH)["checked_rows"] != 9:
        raise ValueError("BILL audited row packet is incomplete")
    packet = json.loads(PACKET_PATH.read_text())
    selection = json.loads(SELECTION_PATH.read_text())
    pair = next(item for item in selection["pairs"] if item["symbol"] == "BILL")
    return packet["source_internal_discrepancy"], pair["periods"]["CY2025_Q2"]


def run_case(template_db: Path, binary: Path, temp_root: str,
             include_conflict: bool) -> dict:
    branch = "both_source_rows" if include_conflict else "one_source_row_only"
    discrepancy, source = bill_source()
    pilot = base.Pilot("bill-" + branch, template_db, binary,
                       temp_root, False, 0.0)
    thesis = must_call(pilot.finance, "thesis_save", {
        "market": "US", "symbol": "BILL", "status": "active", "conviction": 3,
        "thesis": "Revenue quality and operating loss require quarterly review.",
    }, pilot.tenant)["thesis"]
    must_call(pilot.finance, "watchlist_save", {
        "market": "US", "symbol": "BILL", "thesis_id": thesis["id"],
        "event_types": ["earnings"], "keywords": ["BILL"],
        "min_match_score": 1,
    }, pilot.tenant)
    claims = [
        {"metric": "gaap_net_income", "period": "2025-06-30",
         "value": discrepancy[field], "unit": discrepancy["unit"],
         "fact_id": fact_id, "source_sha256": source["sha256"]}
        for field, fact_id in (
            ("statement_of_operations_value", "BILL-JUNE-OPS-NET"),
            ("cash_flow_value", "BILL-JUNE-CF-NET"),
        )
    ]
    alert = must_call(pilot.finance, "event_alert_ingest", {
        "market": "US", "symbol": "BILL", "event": {
            "external_id": source["accession"] + "-" + branch,
            "type": "earnings", "as_of": "2025-06-30",
            "summary": "BILL June-quarter source-row accounting check.",
            "sources": [{"id": source["accession"], "url": source["url"],
                         "sha256": source["sha256"]}],
            "source_claims": claims if include_conflict else claims[:1],
        },
    }, pilot.tenant)["results"][0]["alert"]
    observed_thesis = must_call(pilot.finance, "thesis_get", {
        "thesis_id": thesis["id"],
    }, pilot.tenant)["thesis"]
    review = {
        "thesis_id": thesis["id"], "alert_id": alert["id"],
        "expected_version": observed_thesis["version"],
        "event": {"summary": "Only the stored alert is trusted."},
        "impact": "mixed", "decision": "needs_review" if include_conflict else "maintain",
        "rationale": "The reported net-income row needs source-aware interpretation.",
    }
    calls = [
        local.tool_stream("read-thesis", "finance-tools__thesis_get",
                          {"thesis_id": thesis["id"]}),
        local.tool_stream("read-alert", "finance-tools__alert_list", {}),
    ]
    if include_conflict:
        calls.append(local.tool_stream("bad-upgrade", "finance-tools__thesis_record_review", {
            **review, "decision": "upgrade", "impact": "positive",
            "new_conviction": 4,
        }))
    calls.extend([
        local.tool_stream("save-review", "finance-tools__thesis_record_review", review),
        local.tool_stream("ack-alert", "finance-tools__alert_update", {
            "alert_id": alert["id"], "status": "acknowledged",
            "expected_version": alert["version"],
        }),
    ])
    calls.append(local.text_stream("Local scripted source-conflict replay complete."))

    with local.ScriptedProvider(calls) as provider:
        local.configure_provider(pilot.home, provider.url)
        process, log = base.start_gateway(pilot.home)
        try:
            response = local.gateway_turn(pilot, branch)
        finally:
            base.stop_gateway(process, log)
        provider_calls = provider.received
        unused = len(provider.responses)

    state = pilot.ledger_state()
    stored = state["theses"][0]
    trace = response.get("fastclaw", {}).get("trace", [])
    tool_calls = [item for item in trace if item.get("type") == "tool_call"]
    tool_results = [item for item in trace if item.get("type") == "tool_result"]
    errors = []
    for item in tool_results:
        try:
            payload = json.loads(item.get("result") or "{}")
        except json.JSONDecodeError:
            continue
        errors.extend(error.get("code") for error in payload.get("errors", []))
    final = ((response.get("choices") or [{}])[0].get("message") or {}).get("content")
    expected_tools = 5 if include_conflict else 4
    checks = {
        "local_provider_only": provider_calls == expected_tools + 1 and unused == 0,
        "tool_results_paired": len(tool_calls) == len(tool_results) == expected_tools
            and {item.get("id") for item in tool_calls}
            == {item.get("id") for item in tool_results},
        "source_conflict_matches_branch": len(alert["event"]["unresolved_conflicts"])
            == (1 if include_conflict else 0),
        "review_and_state_match_branch": len(stored["reviews"]) == 1
            and stored["reviews"][0]["decision"] == (
                "needs_review" if include_conflict else "maintain")
            and stored["thesis"]["actionability"] == (
                "blocked" if include_conflict else "available")
            and stored["thesis"]["conviction"] == 3,
        "bad_upgrade_rejected_if_conflict": (
            "decision_on_hold" in errors if include_conflict else not errors),
        "alert_acknowledged": state["alerts"][0]["status"] == "acknowledged",
        "scripted_terminal": final == "Local scripted source-conflict replay complete.",
    }
    return {
        "branch": branch, "checks": checks, "all_checks_passed": all(checks.values()),
        "tool_errors": errors, "provider_requests": provider_calls,
        "tool_calls": len(tool_calls), "tool_results": len(tool_results),
        "conflict_count": len(alert["event"]["unresolved_conflicts"]),
        "review_count": len(stored["reviews"]),
        "decision_hold": stored["thesis"]["decision_hold"],
        "actionability": stored["thesis"]["actionability"],
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
        raise FileNotFoundError("template DB or Gateway binary missing")
    args.output_dir.mkdir(parents=True)
    paths = [Path(__file__), PACKET_PATH, SELECTION_PATH, PLUGIN_PATH,
             Path(local.__file__), Path(base.__file__)]
    manifest = {str(path.relative_to(ROOT)): sha256(path) for path in paths}
    manifest.update(gateway_binary_sha256=sha256(args.gateway_binary),
                    gateway_template_db_sha256=sha256(args.template_db),
                    provider="local_scripted_loopback_no_external_api")
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    with tempfile.TemporaryDirectory(prefix="bill-source-conflict-gateway-") as temp_root:
        results = [run_case(args.template_db, args.gateway_binary, temp_root, conflict)
                   for conflict in (True, False)]
    summary = {
        "status": "free_scripted_bill_same_source_gateway_replay",
        "branches": len(results),
        "all_checks_passed": all(item["all_checks_passed"] for item in results),
        "model_observations": 0, "external_provider_requests": 0,
        "estimated_external_cost_usd": 0,
    }
    for result in results:
        (args.output_dir / (result["branch"] + ".json")).write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    (args.output_dir / "SUMMARY.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    (args.output_dir / "RESULT-SHA256.txt").write_text("".join(
        f"{sha256(path)}  {path.name}\n"
        for path in sorted(args.output_dir.glob("*.json"))))
    print(json.dumps(summary, indent=2))
    if not summary["all_checks_passed"]:
        raise AssertionError("scripted BILL Gateway replay failed")


if __name__ == "__main__":
    main()
