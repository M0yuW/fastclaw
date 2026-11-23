#!/usr/bin/env python3
"""Preflight or run the 30-issuer/150-session source-distinct event arm.

Paid execution requires a fresh authorization flag, a spend ceiling, an unused
output directory, and isolated Gateway inputs. No previous run is resumed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import build_reference_source_distinct_event_fixtures_v1 as source_batch
import run_finance_workflow_flash_panel_v1 as panel
import run_finance_workflow_pilot as base
import run_postcorrection_event_holdout_v4 as prior
import run_reference_insight_citation_development_flash_v2 as citation
import run_reference_insight_development_flash_v1 as reusable
from run_thesis_event_panel import HERE, PLUGIN_PATH, ROOT, sha256
from verify_reference_insight_candidate_v2 import render_reference_card_v2
from workflow_runtime_audit_v2 import audit_turns


NEXT_OBSERVATION_RESERVE_USD = 0.10
PRICING_CHECKED_AT = "2026-10-26"


def source_distinct_prompt(fixture: dict, catalog: dict, thesis_id: str,
                           alert_id: str) -> str:
    return citation.citation_prompt(fixture, catalog, thesis_id, alert_id) + (
        "\n\nHistorical event dates belong in SEC evidence. If you choose to set "
        "next_review_at on the saved research review, it must be in the future "
        "relative to the running Gateway clock; otherwise omit that optional "
        "field. A rejected tool write is not a persisted review. If a tool "
        "rejects the write, inspect the error, correct the input within the "
        "available iteration budget, and verify the actual ledger before "
        "asserting completion. Do not fabricate a review or alert state."
    )


def preflight() -> dict:
    prepared = source_batch.preflight()
    by_case = {fixture["case_id"]: fixture for fixture in prepared["fixtures"]}
    order = []
    for name in prepared["run_order"]:
        case_id, repeat = name.rsplit("-r", 1)
        order.append((by_case[case_id], int(repeat)))
    if len(order) != 150 or len(by_case) != 30:
        raise AssertionError("source-distinct 30 by five order differs")
    return {"prepared": prepared, "order": order}


def manifest_paths(prepared: dict) -> list[Path]:
    frozen = json.loads(source_batch.FREEZE.read_text())
    paths = {
        Path(__file__), Path(source_batch.__file__),
        Path(reusable.__file__), Path(citation.__file__),
        Path(prior.__file__), Path(panel.__file__), Path(base.__file__),
        HERE / "build_reference_insight_prompt_v1.py",
        HERE / "verify_reference_insight_candidate_v1.py",
        HERE / "verify_reference_insight_candidate_v2.py",
        HERE / "screen_reference_insight_semantics_v2.py",
        HERE / "workflow_runtime_audit_v2.py",
        HERE / "prepare_reference_source_distinct_judgment_v1.py",
        HERE / "aggregate_reference_source_distinct_judgments_v1.py",
        HERE / "aggregate_postcorrection_judgments_v2.py",
        HERE / "prepare_postcorrection_judgment_v2.py",
        HERE / "REFERENCE-SOURCE-DISTINCT-INSIGHT-CONFIRMATION-PROTOCOL-v1.md",
        HERE / "INSIGHT-QUALITY-HOLDOUT-RUBRIC-v2.md",
        HERE / "REFERENCE-SOURCE-DISTINCT-CASE-CRITICALS-DRAFT-v1.md",
        source_batch.FREEZE,
        PLUGIN_PATH, PLUGIN_PATH.with_name("accounting_lineage.py"),
        PLUGIN_PATH.with_name("plugin.json"),
    }
    paths.update(HERE / item["path"] for item in frozen["packets"].values())
    if len(prepared["fixtures"]) != 30:
        raise AssertionError("manifest requires the entire source frame")
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--template-db", type=Path)
    parser.add_argument("--gateway-binary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--estimated-spend-cap-usd", type=float)
    parser.add_argument("--authorize-paid-source-distinct-run", action="store_true")
    args = parser.parse_args()
    frozen = preflight()
    prepared = frozen["prepared"]
    if args.preflight_only:
        print(json.dumps({
            "status": "source_distinct_event_arm_ready_but_not_authorized_or_run",
            "issuers": prepared["issuer_cases"],
            "planned_observations": len(frozen["order"]),
            "comparable_rows": prepared["comparable_rows"],
            "run_order_sha256": prepared["run_order_sha256"],
            "source_freeze_sha256": prepared["source_freeze_sha256"],
            "model_requested": prior.MODEL,
            "model_observations": 0, "paid_calls_authorized": False,
        }, indent=2))
        return
    if not args.authorize_paid_source_distinct_run:
        parser.error("separate paid source-distinct authorization required")
    if not all((args.template_db, args.gateway_binary, args.output_dir)):
        parser.error("template DB, Gateway binary and unused output path required")
    if args.estimated_spend_cap_usd is None or not (
            NEXT_OBSERVATION_RESERVE_USD < args.estimated_spend_cap_usd <= 10):
        parser.error("positive bounded incremental estimated-spend cap required")
    if args.output_dir.exists():
        raise ValueError("output path exists; refusing overwrite or implicit resume")
    if not args.template_db.is_file() or not args.gateway_binary.is_file():
        raise FileNotFoundError("Gateway binary or template DB missing")

    base.MODEL, base.PRICING, base.CAP_USD = (
        prior.MODEL, prior.PRICING, args.estimated_spend_cap_usd)
    panel.MODEL = prior.MODEL
    reusable.prompt_contract.reference_prompt = source_distinct_prompt
    reusable.render_reference_card = render_reference_card_v2
    manifest = {str(path.relative_to(ROOT)): sha256(path)
                for path in manifest_paths(prepared)}
    manifest.update(
        model_requested=prior.MODEL,
        model_version_expected=prior.EXPECTED_PROVIDER_VERSION,
        pricing_estimate=prior.PRICING[prior.MODEL],
        pricing_source=prior.PRICING_SOURCE,
        pricing_checked_at=PRICING_CHECKED_AT,
        estimated_spend_stop_usd=args.estimated_spend_cap_usd,
        next_observation_reserve_usd=NEXT_OBSERVATION_RESERVE_USD,
        run_order=prepared["run_order"],
        run_order_sha256=prepared["run_order_sha256"],
        source_freeze_sha256=prepared["source_freeze_sha256"],
        gateway_binary_sha256=sha256(args.gateway_binary),
        gateway_template_db_sha256=sha256(args.template_db),
        source_boundary="30 new issuers; frozen selected SEC exhibit rows only",
        quality_score_stage="post-run claim-level F/I/R/S/U adjudication",
    )
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    prior.write_hash_list(args.output_dir)
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="source-distinct-insight-flash-") as temp:
        for fixture, repetition in frozen["order"]:
            if spent + NEXT_OBSERVATION_RESERVE_USD > args.estimated_spend_cap_usd:
                print("STOP: insufficient estimated reserve", flush=True)
                break
            observation_id = f"{fixture['case_id']}-r{repetition}"
            pilot, process, log = None, None, None
            state, checks, card, error = None, {}, None, None
            try:
                pilot = prior.V4Pilot(observation_id, args.template_db,
                                      args.gateway_binary, temp, False, spent)
                process, log = base.start_gateway(pilot.home)
                state, checks, card = reusable.run_case(
                    pilot, fixture, fixture["catalog"])
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                if pilot is not None:
                    try:
                        state = pilot.ledger_state()
                    except Exception:
                        pass
            finally:
                if process is not None and log is not None:
                    base.stop_gateway(process, log)
            turns = pilot.turns if pilot is not None else []
            runtime = audit_turns(turns)
            cost = pilot.cost if pilot is not None else 0.0
            spent += cost
            mechanical = (error is None and bool(checks)
                          and all(checks.values()) and runtime["clean_completion"])
            candidate = (mechanical and card is not None and
                         card["status"] == "candidate_for_qualitative_review")
            result = {
                "observation_id": observation_id,
                "case_id": fixture["case_id"], "repetition": repetition,
                "workflow": "source_distinct_sec_event_to_research_view",
                "status": "candidate_for_qualitative_review" if candidate else "held",
                "mechanical_pass": mechanical, "quality_pass": None,
                "error": error, "checks": checks, "candidate_card": card,
                "runtime_audit": runtime, "state": state, "turns": turns,
                "estimated_cost_usd": cost,
            }
            directory = args.output_dir / observation_id
            directory.mkdir()
            (directory / "result.json").write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n")
            if pilot is not None and (pilot.home / "finance-tools.db").is_file():
                shutil.copy2(pilot.home / "finance-tools.db",
                             directory / "finance-tools.db")
            prior.write_hash_list(args.output_dir)
            print(json.dumps({"observation_id": observation_id,
                              "status": result["status"], "error": error,
                              "cumulative_estimated_cost_usd": spent}), flush=True)
            if (error or runtime["request_errors"]
                    or runtime["cost_uncertain_sequences"]
                    or runtime["unpriced_sequences"]
                    or spent > args.estimated_spend_cap_usd):
                print("STOP: error, uncertain price or estimated cap", flush=True)
                break
    print(json.dumps({
        "completed": len(list(args.output_dir.glob("*/result.json"))),
        "planned": len(frozen["order"]),
        "estimated_cost_usd": spent,
    }), flush=True)


if __name__ == "__main__":
    main()
